'''script to test the http call for ollama'''


import requests
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

OLLAMA_URL="http://localhost:11434/api/generate"


def ask(prompt:str)->str:
    res=requests.post(OLLAMA_URL,json={"model":config.OLLAMA_MODEL,"prompt":prompt,"stream":False},timeout=60)
    res.raise_for_status()
    return res.json()["response"]


if __name__ =="__main__":
    response=ask("What is the capital of France? Answer in one sentence.")

    print(f"reply: {response}")