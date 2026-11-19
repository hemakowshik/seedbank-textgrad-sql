"""Minimal LLM client for any OpenAI-compatible Chat Completions endpoint (stdlib only).

Providers (choose with --provider; key read from the env var shown):
  groq      https://api.groq.com/openai/v1                          GROQ_API_KEY     (free tier; default openai/gpt-oss-20b)
  gemini    https://generativelanguage.googleapis.com/v1beta/openai  GEMINI_API_KEY   (free tier available)
  openai    https://api.openai.com/v1                                OPENAI_API_KEY
  anthropic https://api.anthropic.com/v1                             ANTHROPIC_API_KEY (OpenAI-compatible endpoint)
  ollama    http://localhost:11434/v1                                (no key, runs locally)
  mock      offline fake model for smoke-testing the pipeline (NOT real results)
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

# If a model is retired, the client asks the provider for its model list and picks the first
# available one from these preferences (then any chat model).
FALLBACKS = {
    "groq": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b", "llama-3.1-8b-instant"],
    "gemini": ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"],
    "openai": ["gpt-4o-mini", "gpt-4.1-mini", "gpt-5-mini"],
    "anthropic": ["claude-haiku-5-5", "claude-sonnet-5-5"],
}
_NON_CHAT = ("whisper", "tts", "guard", "embed", "orpheus", "safeguard", "compound", "image", "audio")

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-20b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "gemini-2.5-flash"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"),
    "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", "claude-haiku-5-5"),
    "ollama": ("http://localhost:11434/v1", None, "qwen2.5-coder:7b"),
}


_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _key_from_file(env_name):
    """Read KEY=VALUE lines from a .env file in the project folder (so keys need not be typed each time)."""
    path = os.path.join(_ROOT, ".env")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() == env_name:
                    return v
    return None


def _clean_key(v):
    if not v:
        return v
    return v.strip().strip('"').strip("'").strip()


def _is_real_key(v):
    if not v or len(v) < 20:
        return False
    low = v.lower()
    return not any(p in low for p in ("your_key", "your-key", "paste", "here", "...", "…", "xxxx"))


def mask(key):
    return (key[:4] + "…" + key[-4:] + f" ({len(key)} chars)") if key and len(key) > 10 else repr(key)


class LLM:
    def __init__(self, provider="groq", model=None, temperature=0.0, base_url=None, api_key=None,
                 max_tokens=4096, min_interval_s=0.0):
        self.provider = provider
        self.calls = 0
        self.prompt_chars = 0
        if provider == "mock":
            self.model = "mock"
            return
        if provider not in PROVIDERS and not base_url:
            raise ValueError(f"unknown provider {provider}; use one of {list(PROVIDERS)} or pass --base-url")
        url, key_env, default_model = PROVIDERS.get(provider, (base_url, None, model))
        self.base_url = (base_url or url).rstrip("/")
        # Key priority: explicit argument > .env file in the project folder > environment variable.
        # Placeholder text (e.g. "your_key") is ignored.
        self.key_source = "argument" if api_key else None
        if not api_key and key_env:
            for source, value in ((".env file", _key_from_file(key_env)),
                                  ("environment variable", os.environ.get(key_env) or os.environ.get(key_env + " "))):
                if _is_real_key(_clean_key(value)):
                    api_key, self.key_source = value, source
                    break
        self.api_key = _clean_key(api_key) if key_env else "ollama"
        self.key_env = key_env
        if key_env and not _is_real_key(self.api_key):
            raise RuntimeError(f"No API key found for '{provider}'. Put the line  {key_env}=your_key  in a file named .env "
                               f"in the project folder, or run:  set {key_env}=your_key  (no spaces, no quotes).")
        self.model = model or default_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def __call__(self, prompt):
        self.calls += 1
        self.prompt_chars += len(prompt)
        if self.provider == "mock":
            return _mock_response(prompt, self.calls)
        wait = self.min_interval_s - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        switched = False
        for attempt in range(6):
            payload = {"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens,
                       "messages": [{"role": "user", "content": prompt}]}
            if "gpt-oss" in self.model:          # reasoning model: keep thinking short so the answer fits
                payload["reasoning_effort"] = "low"
            body = json.dumps(payload).encode()
            req = urllib.request.Request(self.base_url + "/chat/completions", data=body, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "Accept": "application/json",
                                                  "User-Agent": "Mozilla/5.0 (SeedSQL research prototype)",
                                                  "Authorization": f"Bearer {self.api_key}"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = json.loads(r.read().decode())
                self._last = time.time()
                return data["choices"][0]["message"].get("content") or ""
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="ignore")[:300]
                if e.code == 401:
                    raise RuntimeError(self.key_help()) from None
                if e.code in (401, 403):
                    hint = (" (check the API key)" if e.code == 401 else
                            " (blocked by the provider's firewall or the key lacks access)")
                    raise RuntimeError(f"LLM HTTP {e.code}{hint}: {detail}") from None
                if (e.code == 404 or "model_not_found" in detail or "decommissioned" in detail) and not switched:
                    new = self._pick_available_model()
                    if new and new != self.model:
                        print(f"[llm] model '{self.model}' is not available; switching to '{new}'")
                        self.model, switched = new, True
                        continue
                if e.code in (429, 500, 502, 503, 529) and attempt < 5:
                    time.sleep(min(60, 5 * 2 ** attempt))
                    continue
                raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from None
            except urllib.error.URLError as e:
                if attempt < 5:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise RuntimeError(f"LLM connection failed: {e}") from None


    def _pick_available_model(self):
        """Ask the provider which models exist and return the best available one."""
        try:
            req = urllib.request.Request(self.base_url + "/models", headers={
                "Authorization": f"Bearer {self.api_key}", "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (SeedSQL research prototype)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                ids = [m.get("id", "") for m in json.loads(r.read().decode()).get("data", [])]
        except Exception as e:
            print(f"[llm] could not list models: {e}")
            return None
        ids = [i.removeprefix("models/") for i in ids]
        for pref in FALLBACKS.get(self.provider, []):
            if pref in ids:
                return pref
        chat = [i for i in ids if not any(k in i.lower() for k in _NON_CHAT)]
        return chat[0] if chat else None

    def list_models(self):
        req = urllib.request.Request(self.base_url + "/models", headers={
            "Authorization": f"Bearer {self.api_key}", "User-Agent": "Mozilla/5.0 (SeedSQL research prototype)"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return sorted(m.get("id", "") for m in json.loads(r.read().decode()).get("data", []))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise RuntimeError(self.key_help()) from None
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:200]}") from None

    def key_help(self):
        return (f"The {self.provider} API key was rejected (401 Invalid API Key).\n"
                f"  Key used: {mask(self.api_key)}  from: {self.key_source}\n"
                f"  Fix: create a new key (Groq: https://console.groq.com/keys), copy it completely,\n"
                f"  then put the line  {self.key_env}=gsk_...  in the .env file in the project folder\n"
                f"  (or run  set {self.key_env}=gsk_...  with no spaces and no quotes, in the SAME window).")

    def check(self):
        """Validate the key once at startup. Returns None if fine, else a help message."""
        if self.provider in ("mock", "ollama"):
            return None
        try:
            self.list_models()
            return None
        except RuntimeError as e:
            return str(e)
        except Exception as e:
            return f"Could not reach {self.base_url}: {e}"


# ---------------------------------------------------------------- mock model (offline testing only)
def _mock_response(prompt, n):
    """Deterministic fake model: first attempts at hard questions are deliberately broken so that the
    refinement code paths (errors, loss, gradient, step) are exercised. Used ONLY to test the pipeline."""
    from .prompts import BENCH
    if "<IMPROVED_VARIABLE>" in prompt and "textual gradient descent" in prompt:
        var = re.search(r"<VARIABLE>\n([\s\S]*?)\n</VARIABLE>", prompt).group(1)
        return f"<IMPROVED_VARIABLE>{var}\nAlways compute 'most recent' per lot with a correlated MAX(test_date) subquery and use exact stored values.</IMPROVED_VARIABLE>"
    if "computing textual gradients" in prompt:
        return "- The prompt should remind the model to use only existing column names and per-lot MAX(test_date)."
    if "strict reviewer" in prompt:
        return "- Execution failed.\nVERDICT: FAIL" if "status: ERROR" in prompt else "No problems found.\nVERDICT: PASS"
    if "coordinator" in prompt:
        return "Mock summary."
    q = re.search(r"### Question\n([\s\S]*?)\n\nRespond", prompt)
    q = q.group(1).strip() if q else ""
    gold = next((x for x in BENCH["questions"] if x["question"] == q), None)
    refined = "Always compute 'most recent'" in prompt or "Your previous query" in prompt
    if gold is None:
        return "```sql\nSELECT 1;\n```"
    if gold["tier"] == 3 and not refined:
        return "```sql\nSELECT lot_id, germination_score FROM GerminationTest;\n```"  # unknown column
    if gold["tier"] == 2 and "### Examples" not in prompt and gold["id"] in ("T2-02", "T2-03"):
        return "```sql\nSELECT lot_id FROM StorageLog LIMIT 3;\n```"  # wrong result
    return f"```sql\n{gold['gold_sql']}\n```"
