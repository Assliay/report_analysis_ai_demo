import os
from litellm import completion
from dotenv import load_dotenv

load_dotenv()

def get_completion(prompt: str, system_prompt: str = "You are a helpful financial assistant."):
    """
    Unified LLM completion using LiteLLM.
    """
    model = os.getenv("LLM_MODEL", "gpt-4-turbo")
    
    response = completion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        response_format={ "type": "json_object" } # Ensure JSON output
    )
    
    return response.choices[0].message.content
