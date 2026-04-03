"""Thin wrapper for Google Gemini API calls (stdlib only)."""

import json
import os
import sys
import urllib.request
import urllib.error

MODEL = "gemini-2.5-flash"
ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


def _get_api_key():
    """Get the Gemini API key from environment."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        print(
            "Error: set GEMINI_API_KEY or GOOGLE_API_KEY in your environment.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def generate(prompt, system_prompt=None):
    """Call Gemini and return the text response."""
    key = _get_api_key()

    contents = []
    if system_prompt:
        contents.append({
            "role": "user",
            "parts": [{"text": system_prompt}],
        })
        contents.append({
            "role": "model",
            "parts": [{"text": "Understood."}],
        })

    contents.append({
        "role": "user",
        "parts": [{"text": prompt}],
    })

    body = json.dumps({"contents": contents}).encode()

    req = urllib.request.Request(
        f"{ENDPOINT}?key={key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Gemini API error ({e.code}): {error_body}", file=sys.stderr)
        sys.exit(1)

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print(f"Unexpected Gemini response: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
