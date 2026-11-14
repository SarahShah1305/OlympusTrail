"""Print one raw Gemini response for diagnosing LLM parsing."""

import asyncio
import os

import httpx
from dotenv import load_dotenv

from ai_guide.llm_client import _GUIDE_DIR, _call_model, _models
from ai_guide.parser_llm import _JSON_SHAPE, _SYSTEM_PROMPT


async def main() -> None:
    """Send the sample question and print status, model, and raw body."""
    load_dotenv(_GUIDE_DIR / ".env")
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("Error: GEMINI_API_KEY is not configured")
        return

    user = f"{_JSON_SHAPE}\nQuestion: Take me to the nearest ice."
    async with httpx.AsyncClient(timeout=8.0) as client:
        for model in _models():
            try:
                status, raw_text = await _call_model(
                    client,
                    model,
                    api_key,
                    _SYSTEM_PROMPT,
                    user,
                    True,
                )
                print(f"Model: {model}\nHTTP status: {status}\nRaw response text:\n{raw_text}")
                if status == 200:
                    return
            except httpx.HTTPError as exc:
                print(f"Model: {model}\nError: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
