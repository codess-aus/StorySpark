"""Generate new writing prompts using an Azure AI Foundry deployed model.

This script:
1. Reads the existing `docs/prompts.md` file.
2. Finds the AI-GENERATED-PROMPTS markers.
3. Calls the Azure AI Inference Chat Completions API to produce fresh prompts.
4. Appends a dated section between the markers and writes the file back.

Environment Variables (required):
  AZURE_AI_ENDPOINT   - e.g. https://my-ai-resource-endpoint
  AZURE_AI_KEY        - the API key for the Azure AI Inference endpoint
  AZURE_AI_MODEL      - model name (e.g. gpt-4o-mini) or deployment name

Optional CLI args:
  --count N           - number of new prompts to generate (default: 5)
  --dry-run           - print prompts and do not modify file
    --debug             - print raw model output before parsing
    --mock              - generate synthetic prompts without calling the model (for local testing)

Usage (local):
  export AZURE_AI_ENDPOINT=...
  export AZURE_AI_KEY=...
  export AZURE_AI_MODEL=gpt-4o-mini
  python scripts/generate_prompts.py --count 6

GitHub Action will set secrets via repository settings.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional
import socket

# Load local environment variables from .env if present (optional convenience)
try:  # pragma: no cover
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # Safe to ignore if python-dotenv not installed or .env missing

try:
    from azure.ai.inference import ChatCompletionsClient
    from azure.core.credentials import AzureKeyCredential
except ImportError:  # pragma: no cover - allow fallback for Azure OpenAI
    ChatCompletionsClient = None  # type: ignore
    AzureKeyCredential = None  # type: ignore

try:
    import requests  # REST fallback for Azure OpenAI
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

MARKER_START = "<!-- AI-GENERATED-PROMPTS:START -->"
MARKER_END = "<!-- AI-GENERATED-PROMPTS:END -->"
PROMPTS_FILE = os.path.join("docs", "prompts.md")


@dataclass
class GeneratedPrompt:
    title: str
    prompt: str

    def to_markdown(self) -> str:
        safe_title = self.title.strip().replace("\n", " ")
        body = self.prompt.strip()
        return f"\n!!! quote \"{safe_title}\"\n    {body}\n"


def load_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def save_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def extract_existing_generated_section(text: str) -> str:
    pattern = re.compile(re.escape(MARKER_START) + r"(.*?)" + re.escape(MARKER_END), re.DOTALL)
    m = pattern.search(text)
    return m.group(1) if m else ""


def build_system_prompt() -> str:
    return (
        "You are an assistant that produces concise, reflective, inclusive writing prompts about personal life stories. "
        "Return ONLY valid JSON: an array of objects with keys 'title' and 'prompt'. Each 'prompt' should be 1-2 sentences,"
        " encouraging memory recall, introspection, or narrative exploration. Avoid repeating prior prompts. No markdown, no commentary."
    )


def create_messages(existing_snippet: str, count: int) -> List[dict]:
    existing_trimmed = existing_snippet.strip()
    if len(existing_trimmed) > 4000:  # limit token usage
        existing_trimmed = existing_trimmed[-4000:]
    user_content = (
        f"Generate {count} new, unique writing prompts. "
        "They must not duplicate prior prompts. "
        "Focus on memories, turning points, relationships, resilience, identity, gratitude, legacy. "
        "Return JSON only. Here is a sample of previous generated content to avoid duplicates:\n" + existing_trimmed
    )
    # Using dict form accepted by client.complete() to avoid beta model class signature issues.
    return [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": user_content},
    ]


def call_foundry_model(endpoint: str, key: str, model: str, messages: List[dict]) -> str:
    """Invoke Azure AI Foundry inference endpoint via SDK."""
    if ChatCompletionsClient is None or AzureKeyCredential is None:
        raise SystemExit("azure-ai-inference package missing. Install requirements or switch to Azure OpenAI mode.")
    client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    response = client.complete(
        messages=messages,
        model=model,
        temperature=float(os.getenv("STORYSPARK_TEMPERATURE", 0.9)),
        max_tokens=int(os.getenv("STORYSPARK_MAX_TOKENS", 800)),
        top_p=float(os.getenv("STORYSPARK_TOP_P", 0.95)),
    )
    combined = "".join(
        choice.message.content
        for choice in getattr(response, "choices", [])
        if getattr(choice, "message", None) and getattr(choice.message, "content", None)
    )
    return combined.strip()


def call_openai_model(base_endpoint: str, key: str, deployment: str, messages: List[dict], api_version: str) -> str:
    """Call Azure OpenAI (Cognitive Services) Chat Completions REST API."""
    if requests is None:
        raise SystemExit("'requests' not installed. Add it to requirements.txt.")
    url = f"{base_endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
    payload = {
        "messages": messages,
        "temperature": float(os.getenv("STORYSPARK_TEMPERATURE", 0.9)),
        "top_p": float(os.getenv("STORYSPARK_TOP_P", 0.95)),
        "max_tokens": int(os.getenv("STORYSPARK_MAX_TOKENS", 800)),
    }
    headers = {"Content-Type": "application/json", "api-key": key}
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        raise SystemExit(f"Azure OpenAI request failed: {resp.status_code} {resp.text[:400]}")
    data = resp.json()
    combined = "".join(
        choice.get("message", {}).get("content", "")
        for choice in data.get("choices", [])
        if choice.get("message", {}).get("content")
    )
    return combined.strip()


def _classify_endpoint(endpoint: str) -> str:
    if not endpoint:
        raise SystemExit("Endpoint value empty.")
    host = endpoint.strip().split("//", 1)[-1].split("/", 1)[0]
    if "inference.azure.com" in host:
        return "foundry"
    if "cognitiveservices.azure.com" in host or host.endswith(".openai.azure.com"):
        return "openai"
    raise SystemExit("Unrecognized endpoint host; expected inference.azure.com or cognitiveservices.azure.com.")


def parse_json_array(raw: str) -> List[GeneratedPrompt]:
    # Attempt direct parse
    cleaned = raw.strip()
    # Fallback: extract first JSON array subset
    if not cleaned.startswith("["):
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start != -1 and end != -1:
            cleaned = cleaned[start : end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model output was not valid JSON: {e}\nRaw output:\n{raw}") from e
    prompts: List[GeneratedPrompt] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "Untitled Prompt")).strip()
        prompt = str(item.get("prompt", "Write about a meaningful memory.")).strip()
        if title and prompt:
            prompts.append(GeneratedPrompt(title=title, prompt=prompt))
    return prompts


def inject_prompts(original: str, new_prompts_md: str) -> str:
    if MARKER_START not in original or MARKER_END not in original:
        raise RuntimeError("Markers not found in prompts.md; ensure they exist before running.")
    pattern = re.compile(re.escape(MARKER_START) + r"(.*?)" + re.escape(MARKER_END), re.DOTALL)
    dated_header = f"\n\n### AI Generated Prompts - {dt.date.today().isoformat()}\n"
    replacement_block = MARKER_START + dated_header + new_prompts_md + "\n" + MARKER_END
    return pattern.sub(replacement_block, original, count=1)


def _mock_prompts(count: int) -> List[GeneratedPrompt]:
    base_examples = [
        ("A Quiet Turning Point", "Recall a seemingly small moment that later proved pivotal. What shifted afterward?"),
        ("An Object You Still Keep", "Describe an old object you've kept. Why does it matter and what memory does it hold?"),
        ("Gratitude in Difficulty", "Write about a time gratitude appeared during a challenging period. What revealed it?"),
        ("A Voice That Guided You", "Think of someone whose words shaped a choice you made. What did they say?"),
        ("Hidden Joy", "Describe a joy you didn't expect to find in an ordinary routine. Why did it stand out?"),
    ]
    # Rotate / slice to requested count
    out = []
    for i in range(count):
        title, body = base_examples[i % len(base_examples)]
        # Slight variation to avoid identical duplicates
        variant = f"{body}"
        out.append(GeneratedPrompt(title=title, prompt=variant))
    return out


def _write_metadata(mode: str, count: int, model: str, endpoint: Optional[str]) -> None:
    host = "" if not endpoint else endpoint.strip().split("//", 1)[-1].split("/", 1)[0]
    meta = {
        "timestamp": dt.datetime.utcnow().isoformat() + "Z",
        "mode": mode,
        "count": count,
        "model": model,
        "endpoint_host": host,
        "runner_host": socket.gethostname(),
    }
    try:
        with open("prompt_generation_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        print(f"[WARN] Failed to write metadata file: {e}", file=sys.stderr)


def generate(count: int, dry_run: bool = False, debug: bool = False, mock: bool = False) -> None:
    endpoint = os.getenv("AZURE_AI_ENDPOINT") or os.getenv("AZURE_OPENAI_ENDPOINT")
    key = os.getenv("AZURE_AI_KEY") or os.getenv("AZURE_OPENAI_KEY")
    model = os.getenv("AZURE_AI_MODEL") or os.getenv("AZURE_OPENAI_DEPLOYMENT") or "UNSPECIFIED"
    api_version: Optional[str] = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")

    if mock:
        mode = "mock"
        if debug:
            print("[DEBUG] Running in --mock mode; no Azure call will be made.")
    else:
        if not all([endpoint, key, model]):
            missing = [name for name, val in [("AZURE_AI_ENDPOINT", endpoint), ("AZURE_AI_KEY", key), ("AZURE_AI_MODEL", model)] if not val]
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
        mode = _classify_endpoint(endpoint)
        print(f"[MODE] Detected endpoint type: {mode}")
        if len(key.strip()) < 32:
            print("[WARN] API key length seems short; ensure you rotated and copied the full key.", file=sys.stderr)

    original_text = load_file(PROMPTS_FILE)
    existing_generated = extract_existing_generated_section(original_text)

    if mock:
        prompts = _mock_prompts(count)
    else:
        messages = create_messages(existing_generated, count)
        if mode == "foundry":
            raw_output = call_foundry_model(endpoint.rstrip("/"), key, model, messages)
        else:
            base_endpoint = endpoint.split("/openai/")[0].rstrip("/")
            raw_output = call_openai_model(base_endpoint, key, model, messages, api_version)
        if debug:
            print("[DEBUG] Raw model output:\n" + raw_output)
        try:
            prompts = parse_json_array(raw_output)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            raise SystemExit(1)

    if not prompts:
        _write_metadata(mode, 0, model, endpoint)
        raise SystemExit("No prompts parsed from model output.")

    new_md = "".join(p.to_markdown() for p in prompts)
    _write_metadata(mode, len(prompts), model, endpoint)
    print(f"[SUMMARY] Mode={mode} PromptsParsed={len(prompts)} Model={model}")

    if dry_run:
        print("--- DRY RUN: Generated Prompts Markdown ---")
        print(new_md)
        return

    updated = inject_prompts(original_text, new_md)
    save_file(PROMPTS_FILE, updated)
    print(f"Successfully wrote {len(prompts)} prompts to {PROMPTS_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AI writing prompts and update prompts.md")
    parser.add_argument("--count", type=int, default=5, help="Number of prompts to generate (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Print generated prompts without writing file")
    parser.add_argument("--debug", action="store_true", help="Print raw model output (non-mock) before parsing")
    parser.add_argument("--mock", action="store_true", help="Use local synthetic prompts (no Azure call)")
    args = parser.parse_args()
    generate(count=args.count, dry_run=args.dry_run, debug=args.debug, mock=args.mock)


if __name__ == "__main__":  # pragma: no cover
    main()
