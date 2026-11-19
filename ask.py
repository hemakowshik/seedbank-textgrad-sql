"""Ask one question from the terminal and watch the TextGrad refinement trace.

  python ask.py "Which seed lots have a most recent germination rate below 75% and need retesting?" --provider groq
  python ask.py "..." --method zero
"""
import sys, os
if hasattr(sys.stdout, "reconfigure"):  # Windows console: avoid UnicodeEncodeError, enable colours
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
if os.name == "nt":
    os.system("")

import argparse
import textwrap

from seedsql.db import SeedBankDB
from seedsql.llm import LLM
from seedsql.methods import LABELS, run_method

C = {"b": "\033[1m", "g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "c": "\033[36m", "m": "\033[35m", "x": "\033[0m"}


def show_table(res, limit=15):
    if not res["ok"]:
        print(f"{C['r']}ERROR: {res['error']}{C['x']}")
        return
    cols = res["columns"]
    rows = [[("%.2f" % v) if isinstance(v, float) else str(v) for v in r] for r in res["values"][:limit]]
    widths = [min(28, max([len(c)] + [len(r[i]) for r in rows])) for i, c in enumerate(cols)]
    print("  " + " | ".join(c[:w].ljust(w) for c, w in zip(cols, widths)))
    print("  " + "-+-".join("-" * w for w in widths))
    for r in rows:
        print("  " + " | ".join(v[:w].ljust(w) for v, w in zip(r, widths)))
    if len(res["values"]) > limit:
        print(f"  ... {len(res['values'])} rows total")


def on_iter(it):
    print(f"\n{C['b']}── Iteration {it['k']} ─────────────────────────────{C['x']}")
    print(f"{C['c']}[forward] SQL:{C['x']}\n" + textwrap.indent(it["sql"] or "(none)", "  "))
    print(f"{C['g']}[execute]{C['x']}")
    show_table(it["res"], 8)
    if it.get("validation"):
        v = it["validation"]
        print(f"{C['m']}[validator] {v['tests_run']} metamorphic test(s){C['x']}")
        for f in v["findings"] or []:
            print(f"  - [{f['category']}/{f['rule']}/{f['source']}] {f['evidence']}")
        if not v["findings"]:
            print("  no rule violations")
    if it.get("loss"):
        print(f"{C['r']}[loss] {it.get('verdict', '')}{C['x']}\n" + textwrap.indent(it["loss"].strip(), "  "))
    if it.get("gradient"):
        print(f"{C['m']}[∇ gradient on prompt]{C['x']}\n" + textwrap.indent(it["gradient"].strip(), "  "))
    if it.get("new_prompt"):
        print(f"{C['y']}[TGD step] updated prompt:{C['x']}\n" + textwrap.indent(it["new_prompt"].strip(), "  "))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--method", default="textgrad", choices=["zero", "few", "selfcorr", "textgrad", "textgrad_lib", "vg_retry", "vg_textgrad_static", "vg_textgrad"])
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-iters", type=int, default=4)
    a = ap.parse_args()
    llm = LLM(a.provider, a.model)
    out = run_method(a.method, a.question, llm, SeedBankDB(), max_iters=a.max_iters, on_iter=on_iter)
    print(f"\n{C['b']}══ Final answer ({LABELS[a.method]}, {len(out['iterations'])} iteration(s), "
          f"{out['calls']} LLM calls) ══{C['x']}")
    show_table(out["final"]["res"], 50)


if __name__ == "__main__":
    main()
