import os 
from pathlib import Path
import re
import logging
import asyncio
from typing import List, Dict, Any
from groq import AsyncGroq

from backend.app.core.config.config import get_settings
from backend.app.core.interfaces import SentenceCallback, LanguageProfile
from .prompt_builder import build_messages

logger = logging.getLogger(__name__)

class GroqService:
    def __init__(self, session_id: str):
        self.session_id = session_id
        settings = get_settings()
        self.client = AsyncGroq(api_key=settings.groq_api_key)
        self.model = settings.groq_model

        prompt_path = Path(__file__).resolve().parents[2] / "core" / "prompts" / "base_system_prompt.md"
        with open(prompt_path, "r", encoding="utf-8") as file:
            BASE_PROMPT = file.read()

        self.history: List[Dict[str, str]] = [{"role": "system", "content": BASE_PROMPT}]
        self.max_history_turns = settings.groq_max_history
        self._sentence_callbacks: List[SentenceCallback] = []

    def on_sentence(self, callback: SentenceCallback) -> None:
        self._sentence_callbacks.append(callback)

    def _check_split(self, buffer: str, lang_profile: LanguageProfile, is_first_chunk: bool = False) -> tuple[str | None, str]:
        words = buffer.strip().split()
        word_count = len(words)
        if word_count == 0:
            return None, buffer

        primary_delims = lang_profile.chunk_primary_delimiters
        secondary_delims = lang_profile.chunk_secondary_delimiters
        
        # First-chunk latency override: require only 2 words for the first split to minimize TTFT
        min_words = 2 if is_first_chunk else lang_profile.chunk_min_words
        max_words = lang_profile.chunk_max_words

        # Check for primary delimiters (split immediately)
        for i, char in enumerate(buffer):
            if char in primary_delims:
                chunk = buffer[:i + 1]
                rem = buffer[i + 1:]
                return chunk, rem

        # Check for secondary delimiters/conjunction words (split only if min_words reached)
        accumulated_words = []
        current_char_idx = 0
        for w in words:
            accumulated_words.append(w)
            word_start = buffer.find(w, current_char_idx)
            if word_start == -1:
                word_start = current_char_idx
            word_end = word_start + len(w)
            current_char_idx = word_end

            if len(accumulated_words) >= min_words:
                is_secondary = False
                for sd in secondary_delims:
                    if sd.isalpha():
                        if w.lower() == sd.lower():
                            is_secondary = True
                    else:
                        if w.endswith(sd):
                            is_secondary = True
                
                if is_secondary:
                    chunk = buffer[:word_end]
                    rem = buffer[word_end:]
                    return chunk, rem

        # Enforce hard word limit (max_words)
        if word_count >= max_words:
            last_word = words[max_words - 1]
            word_start = buffer.find(last_word)
            if word_start == -1:
                word_start = 0
            word_end = word_start + len(last_word)
            
            chunk = buffer[:word_end]
            rem = buffer[word_end:]
            return chunk, rem

        return None, buffer
    
    async def generate_reply(self, user_text: str, lang_profile: LanguageProfile) -> None:
        if not user_text.strip():
            return
            
        logger.info("[%s] Sending to Groq (%s): %s", self.session_id, lang_profile.code, user_text)
        
        buffer = ""
        full_assistant_reply = ""
        is_first_chunk = True
        
        try:
            api_messages = build_messages(self.history, user_text, lang_profile)
            
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=api_messages,
                stream=True,
                temperature=0.7,
                max_tokens=150
            )
            
            async for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                buffer += token
                full_assistant_reply += token
                
                while True:
                    chunk_to_send, buffer = self._check_split(buffer, lang_profile, is_first_chunk)
                    if chunk_to_send is None:
                        break
                    
                    sentence = chunk_to_send.strip()
                    if sentence:
                        is_first_chunk = False  # Reset first chunk override
                        await self._dispatch_sentence(sentence)
                    
            if buffer.strip():
                await self._dispatch_sentence(buffer.strip())
                
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": full_assistant_reply})

            if len(self.history) > self.max_history_turns + 1:
                self.history = [self.history[0]] + self.history[-self.max_history_turns:]

            logger.debug("[%s] Full Groq reply logged to history.", self.session_id)
            
        except Exception as e:
            logger.exception("[%s] Groq streaming failed: %s", self.session_id, e)
    
    async def _dispatch_sentence(self, sentence: str) -> None:
        for callback in list(self._sentence_callbacks):
            try:
                task = asyncio.create_task(callback(sentence))
                task.add_done_callback(
                    lambda t: logger.error(
                        "[%s] Sentence callback failed: %s",
                        self.session_id,
                        t.exception()
                    ) if not t.cancelled() and t.exception() else None
                )
            except Exception:
                logger.exception("[%s] Sentence callback creation failed.", self.session_id)