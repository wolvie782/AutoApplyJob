"""
Unified AI client — wraps both Anthropic and OpenAI behind one interface.
Set ai.provider in config/config.yaml to "anthropic" or "openai".
"""

import os
from dataclasses import dataclass


@dataclass
class AIConfig:
    provider: str     # "anthropic" or "openai"
    model: str
    humanize: bool
    cover_letter_max_words: int


def get_ai_config(config: dict) -> AIConfig:
    ai = config.get("ai", {})
    provider = ai.get("provider", "anthropic").lower()
    if provider == "openai":
        model = ai.get("openai_model", "gpt-4o-mini")
    else:
        model = ai.get("anthropic_model", "claude-haiku-4-5-20251001")
    return AIConfig(
        provider=provider,
        model=model,
        humanize=ai.get("humanize", True),
        cover_letter_max_words=ai.get("cover_letter_max_words", 250),
    )


def build_client(ai_config: AIConfig):
    """Return the appropriate async client, or None if no key is set."""
    if ai_config.provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=api_key)
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )
    else:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        import anthropic
        return anthropic.AsyncAnthropic(api_key=api_key)


async def complete(client, model: str, system: str, user: str, max_tokens: int = 600) -> str:
    """
    Single unified completion call.
    Works with both AsyncAnthropic and AsyncOpenAI clients.
    """
    class_name = type(client).__name__

    if "Anthropic" in class_name:
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text.strip()

    else:
        # OpenAI
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.choices[0].message.content.strip()
