"""API keys for the optional LLM-backed Judge seat.

The desk runs with **no key at all** -- the default judge is deterministic.
A key is only needed if you want to swap in ``LLMJudge`` and watch the
model's opinion differ from the rule-based one.

Where the key lives
-------------------
In ``.env`` in the repository root. That file is in ``.gitignore``, so it
cannot be committed by accident. The dashboard never renders the key, never
puts it in the report, and never writes it to the journal.

The request shape here is deliberately the same one ``src/policy/judge.py``
uses -- ``POST {base_url}/chat/completions`` with a Bearer token -- so the
"test connection" button tests the thing that will actually be used.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# The providers the repository's .env.example already names, plus a slot for
# any other OpenAI-compatible endpoint.
PROVIDERS: dict[str, dict[str, str]] = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    "Kimi (Moonshot)": {
        "base_url": "https://api.moonshot.cn/v1",
        "model": "moonshot-v1-8k",
        "api_key_env": "KIMI_API_KEY",
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    "Custom (OpenAI-compatible)": {
        "base_url": "",
        "model": "",
        "api_key_env": "LLM_API_KEY",
    },
}

ENV_FILE = ".env"


# ---------------------------------------------------------------- .env I/O
def env_path(repo_root: Path) -> Path:
    return repo_root / ENV_FILE


def read_env(path: Path) -> dict[str, str]:
    """Every KEY=VALUE pair in the file. Comments and blanks are skipped."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def write_env_value(path: Path, name: str, value: str) -> Path:
    """Set one KEY in the .env file, leaving every other line untouched.

    A rewrite that drops the reader's other keys would be a nasty surprise,
    so the file is edited line by line and only the target key is replaced.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=")
    replacement = f"{name}={value}"
    replaced = False
    out: list[str] = []
    for line in lines:
        if pattern.match(line):
            out.append(replacement)
            replaced = True
        else:
            out.append(line)
    if not replaced:
        if out and out[-1].strip():
            out.append("")
        out.append(replacement)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def remove_env_value(path: Path, name: str) -> bool:
    """Delete a KEY from the .env file. Returns True if something was removed."""
    if not path.exists():
        return False
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=")
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not pattern.match(line)]
    if len(kept) == len(lines):
        return False
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")
    return True


def mask(value: str) -> str:
    """Show enough of a key to recognise it and not enough to use it."""
    if not value:
        return ""
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


# --------------------------------------------------------------- connection
def _scrub(text: str, secret: str) -> str:
    """Remove the key from any text that came back from the provider.

    A provider's error body echoes the request, and a request carries the
    key. Showing that verbatim would put the key on the screen.
    """
    if secret:
        text = text.replace(secret, "***")
    return text


def test_connection(base_url: str, model: str, api_key: str, timeout_s: float = 30.0) -> tuple[bool, str]:
    """Make one minimal chat-completions call. Returns (ok, message).

    The same request shape the judge uses, with the smallest possible
    payload. It costs a fraction of a cent and it proves the key, the
    endpoint and the model name all work together.
    """
    if not base_url:
        return False, "No base URL. Pick a provider, or fill in a custom one."
    if not model:
        return False, "No model name."
    if not api_key:
        return False, "No API key."

    endpoint = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 16,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "Reply with strict JSON only."},
            {"role": "user", "content": '{"ping":"pong"}'},
        ],
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
        except Exception:
            detail = exc.reason if hasattr(exc, "reason") else ""
        return False, f"HTTP {exc.code} from the provider. {_scrub(str(detail), api_key)}"
    except urllib.error.URLError as exc:
        return False, f"Could not reach the endpoint: {_scrub(str(exc.reason), api_key)}"
    except Exception as exc:  # noqa: BLE001 - surfaced to the user, not swallowed
        return False, f"{type(exc).__name__}: {_scrub(str(exc), api_key)}"

    try:
        parsed: dict[str, Any] = json.loads(raw)
        reply = parsed["choices"][0]["message"]["content"]
    except Exception:
        reply = raw[:200]
    return True, f"Connected. The model replied: {str(reply)[:160]}"


def judge_from_env(provider: dict[str, str]) -> Any:
    """Build an LLMJudge from the environment, or None if it cannot run.

    The key is read from the process environment, which is where the judge
    looks for it. The dashboard sets ``os.environ`` for the duration of the
    call, so nothing is written to disk just to make one call.
    """
    from src.policy.judge import LLMJudge

    key = os.environ.get(provider["api_key_env"], "")
    if not key:
        return None
    return LLMJudge(
        model_name=provider.get("api_key_env", "llm").lower(),
        base_url=provider["base_url"],
        model=provider["model"],
        api_key_env=provider["api_key_env"],
    )
