"""Minimal LLM client for any OpenAI-compatible Chat Completions endpoint (stdlib only).

Providers (choose with --provider; key read from the env var shown):
  groq      https://api.groq.com/openai/v1                          GROQ_API_KEY     (free tier available)
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

PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "llama-3.1-8b-instant"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "gemini-2.0-flash"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"),
    "anthropic": ("https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", "claude-haiku-5-5"),
    "ollama": ("http://localhost:11434/v1", None, "qwen2.5-coder:7b"),
}


class LLM:
    def __init__(self, provider="groq", model=None, temperature=0.0, base_url=None, api_key=None,
                 max_tokens=1024, min_interval_s=0.0):
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
        self.api_key = api_key or (os.environ.get(key_env) if key_env else "ollama")
        if key_env and not self.api_key:
            raise RuntimeError(f"Set the {key_env} environment variable for provider '{provider}'.")
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
        body = json.dumps({"model": self.model, "temperature": self.temperature, "max_tokens": self.max_tokens,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        for attempt in range(6):
            req = urllib.request.Request(self.base_url + "/chat/completions", data=body, method="POST",
                                         headers={"Content-Type": "application/json",
                                                  "Accept": "application/json",
                                                  "User-Agent": "Mozilla/5.0 (SeedSQL research prototype)",
                                                  "Authorization": f"Bearer {self.api_key}"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = json.loads(r.read().decode())
                self._last = time.time()
                return data["choices"][0]["message"]["content"] or ""
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="ignore")[:300]
                if e.code in (401, 403):
                    hint = (" (check the API key)" if e.code == 401 else
                            " (blocked by the provider's firewall or the key lacks access)")
                    raise RuntimeError(f"LLM HTTP {e.code}{hint}: {detail}") from None
                if e.code in (429, 500, 502, 503, 529) and attempt < 5:
                    time.sleep(min(60, 5 * 2 ** attempt))
                    continue
                raise RuntimeError(f"LLM HTTP {e.code}: {detail}") from None
            except urllib.error.URLError as e:
                if attempt < 5:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise RuntimeError(f"LLM connection failed: {e}") from None


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
