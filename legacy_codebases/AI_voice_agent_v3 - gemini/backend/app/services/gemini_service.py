import os 
from pathlib import Path
import re
import logging
import asyncio
from typing import Callable, Awaitable, List, Dict, Any, Tuple, Optional
from google import genai
from google.genai import types

from backend.app.core.config.config import get_settings

logger = logging.getLogger(__name__)

class GeminiService:
    # Connects to Gemini, selects the model, and builds the chat history.
    def __init__(self, session_id: str):
        self.session_id = session_id

        settings = get_settings() #get validated settings from config.py
        
        # Initialize the official Google GenAI client
        # In google-genai, the Client is initialized with api_key.
        # Its async operations are accessed via `client.aio`.
        self.client = genai.Client(api_key=settings.gemini_api_key)

        # Read model and history settings from the validated settings
        self.model = settings.gemini_model

        # Dynamically load the prompt from the MD file
        prompt_path = Path(__file__).resolve().parents[1] / "core" / "prompts" / "retail_prompt.md"
        with open(prompt_path, "r", encoding="utf-8") as file:
            SYSTEM_PROMPT = file.read()

        # Initialize system prompt and history
        # Note: Gemini uses system_instruction in GenerateContentConfig.
        self.system_prompt = SYSTEM_PROMPT
        self.history: List[Dict[str, str]] = []
        self.max_history_turns = settings.gemini_max_history

        # Observer pattern: List of functions waiting for a complete sentence
        self._sentence_callbacks: List[Callable[[str], Awaitable[None] | None]] = []

    def on_sentence(self, callback: Callable[[str], Awaitable[None] | None]) -> None:
        """Register a downstream function (like TTS) to receive completed sentences."""
        self._sentence_callbacks.append(callback)

    # the sentence chunker uses aggressive punctuation and conjunction rules to detect completed segments
    def _find_chunk_split(self, text: str) -> Optional[Tuple[int, bool]]:
        """Analyzes the text buffer and returns (split_index, include_separator) of the earliest split point.

        - split_index (int): The index at which to split the text.
        - include_separator (bool): If True, split after the separator.
                                    If False, split before the separator.
        """
        candidates = []

        # 1. Check for Terminal Punctuation: . ? ! ۔ ؟
        for match in re.finditer(r'([.?!۔؟])(?:\s+|$)', text):
            candidates.append((match.end(1), True))

        words = text.split()
        word_count = len(words)

        # 2. Check for Pause/Clause separators: , ، ; ؛ :
        if word_count >= 3:
            for match in re.finditer(r'([,،;؛:])\s+', text):
                left_words = text[:match.start()].split()
                if len(left_words) >= 3:
                    candidates.append((match.end(1), True))

        # 3. Check for Conjunctions (Urdu and English): اور, لیکن, کیونکہ, یا, پھر, تو, and, but, so, or
        if word_count >= 4:
            for match in re.finditer(r'(\s+)(اور|لیکن|کیونکہ|یا|پھر|تو|and|but|so|or)\s+', text, re.IGNORECASE):
                left_words = text[:match.start()].split()
                if len(left_words) >= 3:
                    candidates.append((match.start(1), False))

        # 4. Max Word Count Limit (aggressive length fallback):
        if word_count >= 10:
            space_indices = [i for i, char in enumerate(text) if char.isspace()]
            if len(space_indices) >= 9:
                candidates.append((space_indices[8], True))

        if not candidates:
            return None

        # Filter out split indices that are 0 (e.g. leading spaces) to prevent loops
        valid_candidates = [c for c in candidates if c[0] > 0]
        if not valid_candidates:
            return None

        return min(valid_candidates, key=lambda x: x[0])
    
#===============================================================================================================#
    # AI streaming
    async def generate_reply(self, user_text: str) -> None:
        """Streams the LLM reply, buffering tokens into complete sentences."""
        # 1. Ignore empty transcripts (background noise) - save tokens
        if not user_text.strip():
            return
            
        logger.info("[%s] Sending to Gemini: %s", self.session_id, user_text)
        
        # 2. Append user message to history
        self.history.append({"role": "user", "content": user_text})
       
        buffer = ""
        full_assistant_reply = ""
        
        try:
            # Construct Gemini content list from history
            # Gemini roles are strictly 'user' and 'model'
            gemini_contents = []
            for msg in self.history:
                role = "user" if msg["role"] == "user" else "model"
                gemini_contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg["content"])]
                    )
                )

            # Define client generation config with system instruction
            config = types.GenerateContentConfig(
                system_instruction=self.system_prompt,
                temperature=0.7,
                max_output_tokens=1000
            )

            # 4. initiate stream with Gemini using client.aio
            stream = await self.client.aio.models.generate_content_stream(
                model=self.model,
                contents=gemini_contents,
                config=config
            )
            
            # 5. Buffering loop - runs whenever Gemini pushes new pieces of text
            async for chunk in stream:
                token = chunk.text or ""
                buffer += token
                full_assistant_reply += token
                
                # Check for splits dynamically in the buffer
                while True:
                    split_info = self._find_chunk_split(buffer)
                    if not split_info:
                        break
                    
                    split_idx, include_separator = split_info
                    chunk_text = buffer[:split_idx].strip()
                    buffer = buffer[split_idx:]
                    
                    if chunk_text:
                        await self._dispatch_sentence(chunk_text)
                    
            # 6. clean anything left in the buffer after the stream closes - fallback
            if buffer.strip():
                await self._dispatch_sentence(buffer.strip())
                
            # 7. save full AI reply to the history
            self.history.append({"role": "model", "content": full_assistant_reply})

            # 3. Prune history to stay within the max_history limit
            # Since history only contains 'user' and 'model' entries, we keep the last max_history_turns messages.
            if len(self.history) > self.max_history_turns:
                self.history = self.history[-self.max_history_turns:]

            logger.debug("[%s] Full Gemini reply logged to history.", self.session_id)
            
        except Exception as e:
            logger.exception("[%s] Gemini streaming failed: %s", self.session_id, e)
   
    # dispatcher - send the ai response to tts 
    async def _dispatch_sentence(self, sentence: str) -> None:
        """Fires the completed sentence to all registered callbacks."""
        for callback in list(self._sentence_callbacks):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(sentence)
                else:
                    callback(sentence)
            except Exception:
                logger.exception("[%s] Sentence callback failed.", self.session_id)
