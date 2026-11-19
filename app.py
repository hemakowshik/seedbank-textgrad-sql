"""SeedSQL local platform: opens the full web interface in your browser, powered by your own LLM API key.

  set GROQ_API_KEY=gsk_...            (Windows CMD;  macOS/Linux: export GROQ_API_KEY=...)
  python app.py                       -> opens http://localhost:8000
  python app.py --provider gemini     (needs GEMINI_API_KEY)
  python app.py --provider ollama --model qwen2.5-coder:7b
  python app.py --provider mock       (offline fake model, for checking the UI only)

SQLite runs in the browser page; this server only serves the page and relays LLM calls,
so your API key never reaches the browser.
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from seedsql.llm import LLM

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "web", "index.html")
LOCK = threading.Lock()


def make_handler(llm):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html") or self.path.startswith("/#"):
                with open(PAGE, "rb") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            elif self.path == "/api/health":
                self._send(200, {"provider": llm.provider, "model": llm.model})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/api/llm":
                return self._send(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                prompt = json.loads(self.rfile.read(n) or b"{}").get("prompt", "")
                with LOCK:  # one call at a time keeps us inside free-tier rate limits
                    text = llm(prompt)
                self._send(200, {"text": text})
            except Exception as e:
                msg = str(e)
                print("LLM error:", msg)
                self._send(429 if "429" in msg else 502, {"error": msg})

        def log_message(self, fmt, *args):
            if "/api/llm" in (args[0] if args else ""):
                print(f"  LLM call #{llm.calls}")

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model", default=None)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--min-interval", type=float, default=1.0, help="seconds between LLM calls")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not os.path.exists(PAGE):
        sys.exit("web/index.html is missing - run: python web/build.py")
    try:
        llm = LLM(a.provider, a.model, base_url=a.base_url, min_interval_s=a.min_interval)
    except Exception as e:
        sys.exit(f"Could not start: {e}")
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(llm))
    url = f"http://localhost:{a.port}/"
    print(f"SeedSQL running at {url}   (LLM: {llm.provider} / {llm.model})")
    print("Keep this window open. Press Ctrl+C to stop.")
    if not a.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
