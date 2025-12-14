import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def get_llm():
    """Returns a ChatOpenAI instance configured for OpenRouter."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not found in .env")

    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        # We use Claude 3.5 Sonnet as it is currently SOTA for coding/agents
        model="anthropic/claude-3.5-sonnet",
        temperature=0,
        max_tokens=2048 # Limit output to prevent 402 errors
    )