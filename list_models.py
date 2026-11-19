"""Show which models your API key can use.   python list_models.py --provider groq"""
import argparse, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from seedsql.llm import LLM
ap = argparse.ArgumentParser(); ap.add_argument("--provider", default="groq"); a = ap.parse_args()
from seedsql.llm import mask
try:
    llm = LLM(a.provider)
    print(f"Provider: {a.provider} | default model: {llm.model} | key: {mask(llm.api_key)} from {llm.key_source}")
    models = llm.list_models()
except RuntimeError as e:
    sys.exit("\n" + str(e))
print("API key OK. Available models:")
for m in models:
    print("  ", m)
