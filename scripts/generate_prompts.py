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
from typing import List

try:
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import ChatRequestMessage
    from azure.core.credentials import AzureKeyCredential
except ImportError as e:  # pragma: no cover - dependency should exist after pip install
    print("Missing Azure AI packages. Did you install requirements?", file=sys.stderr)
    raise

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


def create_messages(existing_snippet: str, count: int) -> List[ChatRequestMessage]:
    existing_trimmed = existing_snippet.strip()
    if len(existing_trimmed) > 4000:  # limit token usage
        existing_trimmed = existing_trimmed[-4000:]
    user_content = (
        f"Generate {count} new, unique writing prompts. "
        "They must not duplicate prior prompts. "
        "Focus on memories, turning points, relationships, resilience, identity, gratitude, legacy. "
        "Return JSON only. Here is a sample of previous generated content to avoid duplicates:\n" + existing_trimmed
    )
    return [
        ChatRequestMessage(role="system", content=build_system_prompt()),
        ChatRequestMessage(role="user", content=user_content),
    ]


def call_model(endpoint: str, key: str, model: str, messages: List[ChatRequestMessage]) -> str:
    """Invoke the Azure AI Inference chat completion endpoint using beta SDK.

    The beta client exposes a .complete(...) method that accepts messages list and parameters directly.
    """
    client = ChatCompletionsClient(endpoint=endpoint, credential=AzureKeyCredential(key))
    response = client.complete(
        messages=messages,
        model=model,
        temperature=0.9,
        max_tokens=800,
        top_p=0.95,
    )
    combined = "".join(
        choice.message.content
        for choice in getattr(response, "choices", [])
        if getattr(choice, "message", None) and getattr(choice.message, "content", None)
    )
    return combined.strip()


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


def generate(count: int, dry_run: bool = False) -> None:
    endpoint = os.getenv("AZURE_AI_ENDPOINT")
    key = os.getenv("AZURE_AI_KEY")
    model = os.getenv("AZURE_AI_MODEL")
    if not all([endpoint, key, model]):
        missing = [name for name, val in [("AZURE_AI_ENDPOINT", endpoint), ("AZURE_AI_KEY", key), ("AZURE_AI_MODEL", model)] if not val]
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    original_text = load_file(PROMPTS_FILE)
    existing_generated = extract_existing_generated_section(original_text)
    messages = create_messages(existing_generated, count)
    raw_output = call_model(endpoint, key, model, messages)
    try:
        prompts = parse_json_array(raw_output)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1)

    if not prompts:
        raise SystemExit("No prompts parsed from model output.")

    new_md = "".join(p.to_markdown() for p in prompts)

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
    args = parser.parse_args()
    generate(count=args.count, dry_run=args.dry_run)


if __name__ == "__main__":  # pragma: no cover
    main()
