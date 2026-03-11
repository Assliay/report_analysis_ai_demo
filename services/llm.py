import os
import time
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

def get_completion(prompt: str, system_prompt: str = "You are a helpful financial assistant."):
    """
    Unified LLM completion using LiteLLM with fallback logic, 
    extended timeout, and TPM optimization.
    """
    primary_model = os.getenv("LLM_MODEL")
    fallback_model = os.getenv("FALLBACK_MODEL")
    api_base = os.getenv("OPENAI_API_BASE")
    
    # Increase timeout to 2x (Default is usually 60s, setting to 300s for stability)
    timeout = 300 
    
    models = [primary_model]
    if fallback_model:
        models.append(fallback_model)
    
    # Retry logic for RateLimit errors (TPM optimization)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = completion(
                model=primary_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                api_base=api_base,
                fallbacks=models[1:] if len(models) > 1 else None,
                response_format={ "type": "json_object" },
                timeout=timeout,
                num_retries=2 # LiteLLM internal retries
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"Rate limit hit, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e
