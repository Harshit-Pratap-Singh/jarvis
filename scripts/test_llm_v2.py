"""script to test the http call for ollama streams"""

import requests
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OLLAMA_URL = "http://localhost:11434/api/generate"
# SYSTEM_PROMPT = """CRITICAL: Maximum 2 sentences. Stop after 2 sentences, no matter what.
# You are a helpful voice assistant. Answer in 1-2 short sentences.Never use bullet points, asterisks, headers, or markdown formatting — your response will be read aloud. Speak naturally and conversationally."""

SYSTEM_PROMPT="""You are a helpful voice assistant. Your response will be read aloud, so:
- Answer in 1-2 short sentences.
- No bullets, asterisks, headers, or markdown.
- Speak naturally and conversationally.

Example of good output:

User: How do I make tea?
Assistant: Boil some water, steep tea leaves or a tea bag for a few minutes, then add milk or sugar if you like.
"""


def ask(prompt: str) -> str:
    output_string = ""
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": config.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": True,
            "system": SYSTEM_PROMPT,
        },
        timeout=60,
        stream=True,
    )

    response.raise_for_status()

    for item in response.iter_lines():
        if not item:
            continue

        chunk = json.loads(item)
        print(chunk["response"], end="", flush=True)
        output_string += chunk["response"]
        if chunk["done"]:
            print()
            break

    return output_string


if __name__ == "__main__":
    # response = ask("What is hate? Answer in 1000 sentence.")
    response = ask("How does a microwave work?")

    # print(f"reply: {response}")
