import logging
from typing import List, Dict, Any
from backend.app.core.config.language_registry import LanguageProfile

logger = logging.getLogger(__name__)

def build_messages(
    history: List[Dict[str, str]], 
    user_text: str, 
    lang_profile: LanguageProfile
) -> List[Dict[str, str]]:
    
    # 1. The permanent base prompt (always history[0])
    base_prompt = history[0]
    
    # 2. The actual conversation history
    conversation_history = history[1:]
    
    # 3. The ephemeral directive (moved to the bottom!)
    ephemeral_directive = {
        "role": "system", 
        "content": lang_profile.llm_directive_text
    }
    
    # 4. The current user turn
    current_turn = {"role": "user", "content": user_text}
    
    # NEW ORDER: [Base, ...History, Directive, User]
    # The LLM sees the language rule literally 1 message before the user speaks.
    return [base_prompt, *conversation_history, ephemeral_directive, current_turn]