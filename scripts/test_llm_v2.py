"""script to test the http call for ollama streams"""

import requests
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OLLAMA_URL = "http://localhost:11434/api/generate"


def ask(prompt: str) -> str:
    output_string = ""
    response = requests.post(
        OLLAMA_URL,
        json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": True},
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
    response = ask("What is hate? Answer in 1000 sentence.")
    # print(f"reply: {response}")
