import os
import time
import sys
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

def get_completion(prompt: str, system_prompt: str = "You are a helpful financial assistant."):
    """
    Unified LLM completion using LiteLLM with fallback logic.
    """
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
                api_base=api_base,
                api_key=os.getenv("OPENAI_API_KEY"),
                fallbacks=models[1:] if len(models) > 1 else None,
                temperature=0.1,
                timeout=timeout,
                num_retries=2
            )
            content = response.choices[0].message.content
            # 清理 Markdown 代码块
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                content = "\n".join(lines).strip()
            return content
        except Exception as e:
            error_msg = str(e).lower()
            # 检测是否是未实名认证导致的硬性 403 限制
            if "rpm limit exceeded" in error_msg and "identity verification" in error_msg:
                print(f"⚠️ [LLM 降级] 主模型因未实名认证触发 403 频率限制。立即切换至降级模型: {fallback_model}")
                sys.stdout.flush()
                # 如果存在 fallback 模型，直接递归调用自身并传入 fallback 列表的下一项
                if fallback_model and primary_model != fallback_model:
                    try:
                        return get_fallback_completion(prompt, system_prompt, fallback_model, api_base, timeout)
                    except Exception as fallback_e:
                        raise Exception(f"Fallback model also failed: {fallback_e}")
                else:
                    raise Exception("No fallback model available or fallback also failed RPM limits.")
                    
            # 针对其他暂时的 403 / 429 增加等待时间
            if ("rate_limit" in error_msg or "403" in error_msg or "429" in error_msg) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"Retrying in {wait_time}s... Error: {e}")
                sys.stdout.flush()
                time.sleep(wait_time)
            else:
                print(f"❌ LLM Error: {e}")
                sys.stdout.flush()
                raise e

def get_fallback_completion(prompt: str, system_prompt: str, fallback_model: str, api_base: str, timeout: int):
    """
    专门处理硬性 403 降级的兜底 LLM 请求。
    """
    print(f"DEBUG: Using Fallback Model: {fallback_model}")
    sys.stdout.flush()
    response = completion(
        model=fallback_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        api_base=api_base,
        api_key=os.getenv("OPENAI_API_KEY"),
        temperature=0.1,
        timeout=timeout,
        num_retries=2
    )
    content = response.choices[0].message.content
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content
