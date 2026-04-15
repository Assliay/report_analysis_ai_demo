import os
import time
import sys
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

import os
import time
import sys
import asyncio
from typing import List, Optional
from litellm import completion, acompletion
from dotenv import load_dotenv

load_dotenv()

def get_completion(prompt: str, system_prompt: str = "You are a helpful financial assistant."):
    """
    Unified LLM completion using LiteLLM with fallback logic (Synchronous).
    """
    # ... existing implementation ...
    primary_model = os.getenv("LLM_MODEL")
    fallback_model = os.getenv("FALLBACK_MODEL")
    api_base = os.getenv("OPENAI_API_BASE")
    
    timeout = 300 
    
    models = [primary_model]
    if fallback_model:
        models.append(fallback_model)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"DEBUG: LLM Request to {primary_model} (Attempt {attempt+1})")
            sys.stdout.flush()
            
            response = completion(
                model=primary_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                api_base=api_base if not primary_model.startswith("gemini") else None,
                fallbacks=models[1:] if len(models) > 1 else None,
                temperature=0.1,
                timeout=timeout,
                num_retries=2
            )
            content = response.choices[0].message.content
            return _clean_markdown(content)
        except Exception as e:
            if _should_retry(e, attempt, max_retries):
                _handle_wait(attempt)
            else:
                raise e

async def aget_completion(prompt: str, system_prompt: str = "You are a helpful financial assistant."):
    """
    Async version of get_completion for concurrent execution.
    """
    primary_model = os.getenv("LLM_MODEL")
    fallback_model = os.getenv("FALLBACK_MODEL")
    api_base = os.getenv("OPENAI_API_BASE")
    timeout = 300
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await acompletion(
                model=primary_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                api_base=api_base if not primary_model.startswith("gemini") else None,
                fallbacks=[fallback_model] if fallback_model else None,
                temperature=0.1,
                timeout=timeout,
                num_retries=2
            )
            return _clean_markdown(response.choices[0].message.content)
        except Exception as e:
            if _should_retry(e, attempt, max_retries):
                wait_time = (attempt + 1) * 5
                await asyncio.sleep(wait_time)
            else:
                raise e

def _clean_markdown(content: str) -> str:
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content

def _should_retry(e: Exception, attempt: int, max_retries: int) -> bool:
    error_msg = str(e).lower()
    if "rpm limit exceeded" in error_msg and "identity verification" in error_msg:
        print(f"⚠️ [LLM 降级] 主模型因未实名认证触发 403 频率限制。需要切降级模型。")
        sys.stdout.flush()
        return True # 我们也当做可重试，让 fallbacks 生效，但其实 Litellm 的 fallbacks 会自己接管。
    return ("rate_limit" in error_msg or "403" in error_msg or "429" in error_msg) and attempt < max_retries - 1

def _handle_wait(attempt: int):
    wait_time = (attempt + 1) * 10
    print(f"Retrying in {wait_time}s...")
    sys.stdout.flush()
    time.sleep(wait_time)

def get_fallback_completion(prompt: str, system_prompt: str, fallback_model: str, api_base: str, timeout: int):
    # (Kept for compatibility if needed, but the logic is now shared)
    return get_completion(prompt, system_prompt)
