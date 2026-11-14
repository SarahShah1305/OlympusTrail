"""Run the sample questions through the LLM parser."""

import asyncio

from ai_guide.parser_llm import parse_question


QUESTIONS = [
    "What's the safest route with 4 hours of oxygen?",
    "Take me to the nearest ice.",
    "How do I get from the base to the closest shelter?",
    "Find a route to ice that avoids radiation.",
    "I only have 2 hours of oxygen and 40% battery. Can I reach ice?",
    "Avoid steep slopes and dust. Go to the best base site.",
    "Where should we build the base?",
    "What's the shortest path to a lava tube?",
    "Route me to ice, but I'm worried about the cold.",
    "What's the weather on Earth today?",
]


async def main() -> None:
    """Print each sample parse or its error."""
    for question in QUESTIONS:
        try:
            result = await parse_question(question)
            print(f"{question}\n{result.model_dump_json() if hasattr(result, 'model_dump_json') else result.json()}")
        except Exception as exc:
            print(f"{question}\nError: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
