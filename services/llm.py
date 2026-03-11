import os
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
    
    models = [primary_model]
    if fallback_model:
        models.append(fallback_model)
    
    # Use completion with fallbacks
    response = completion(
        model=primary_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        api_base=api_base,
        fallbacks=models[1:] if len(models) > 1 else None,
        response_format={ "type": "json_object" }
    )
    
    return response.choices[0].message.content
