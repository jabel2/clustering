#!/usr/bin/env python
"""Diagnose Ollama connection issues."""

import ollama

print("Testing Ollama connection...")

try:
    client = ollama.Client(host="http://localhost:11434")

    print("\n1. Listing models...")
    models = client.list()
    print(f"   Raw response: {models}")

    if "models" in models:
        print(f"\n2. Available models:")
        for m in models["models"]:
            print(f"   - {m.get('name', m)}")
    else:
        print(f"   Models key not found. Keys: {models.keys()}")

    print("\n3. Testing chat with gpt-oss:20b...")
    response = client.chat(
        model="gpt-oss:20b",
        messages=[{"role": "user", "content": "Say hello in 5 words or less."}],
    )
    print(f"   Response: {response['message']['content']}")
    print("\nSuccess! Ollama is working.")

except Exception as e:
    print(f"\nError: {type(e).__name__}: {e}")
