"""The four compared approaches. `textgrad` here is a transparent re-implementation of TextGrad's
forward -> loss -> backward -> TGD-step loop (identical to the web demo). See textgrad_lib.py for the
same loop built on the official `textgrad` package."""
import re

from .db import extract_sql
from .prompts import (BASE_INSTRUCTIONS, generator_prompt, gradient_prompt, loss_prompt, retry_prompt,
                      step_prompt)

METHODS = ["zero", "few", "selfcorr", "textgrad"]
LABELS = {"zero": "Zero-shot", "few": "Few-shot", "selfcorr": "Error-retry", "textgrad": "TextGrad",
          "textgrad_lib": "TextGrad (library)"}


def _passed(res, loss):
    return bool(res["ok"]) and re.search(r"VERDICT:\s*PASS", loss or "", re.I) is not None \
        and re.search(r"VERDICT:\s*FAIL", loss or "", re.I) is None


def run_method(method, question, llm, db, max_iters=4, initial_instructions=BASE_INSTRUCTIONS,
               carry=False, on_iter=None):
    calls0 = llm.calls
    iters = []

    def push(it):
        iters.append(it)
        if on_iter:
            on_iter(it)

    if method in ("zero", "few"):
        sql = extract_sql(llm(generator_prompt(BASE_INSTRUCTIONS, question, method == "few")))
        push({"k": 1, "prompt": BASE_INSTRUCTIONS, "sql": sql, "res": db.run(sql)})

    elif method == "selfcorr":
        prev_sql = prev_res = None
        for k in range(1, max_iters + 1):
            p = generator_prompt(BASE_INSTRUCTIONS, question) if k == 1 else retry_prompt(question, prev_sql, prev_res)
            sql = extract_sql(llm(p))
            res = db.run(sql)
            it = {"k": k, "prompt": BASE_INSTRUCTIONS if k == 1 else "(previous SQL + raw error appended)",
                  "sql": sql, "res": res}
            if not res["ok"]:
                it["loss"] = "Execution error fed back verbatim: " + res["error"]
            push(it)
            if res["ok"]:
                break
            prev_sql, prev_res = sql, res

    elif method == "textgrad":
        instructions = initial_instructions
        for k in range(1, max_iters + 1):
            sql = extract_sql(llm(generator_prompt(instructions, question)))          # forward
            res = db.run(sql)                                                          # execute
            loss = llm(loss_prompt(question, sql, res))                                # loss
            it = {"k": k, "prompt": instructions, "sql": sql, "res": res, "loss": loss,
                  "verdict": "PASS" if _passed(res, loss) else "FAIL"}
            if it["verdict"] == "PASS" or k == max_iters:
                push(it)
                break
            it["gradient"] = llm(gradient_prompt(instructions, question, sql, res, loss))  # backward
            step = llm(step_prompt(instructions, it["gradient"], carry))                    # TGD step
            m = re.search(r"<IMPROVED_VARIABLE>([\s\S]*?)</IMPROVED_VARIABLE>", step, re.I)
            it["new_prompt"] = (m.group(1) if m else step).strip()
            instructions = it["new_prompt"]
            push(it)
        return {"method": method, "iterations": iters, "final": iters[-1], "calls": llm.calls - calls0,
                "final_instructions": instructions}

    elif method == "textgrad_lib":
        from .textgrad_lib import run_textgrad_library
        return run_textgrad_library(question, llm, db, max_iters=max_iters,
                                    initial_instructions=initial_instructions, on_iter=on_iter)
    else:
        raise ValueError(method)

    return {"method": method, "iterations": iters, "final": iters[-1], "calls": llm.calls - calls0}
