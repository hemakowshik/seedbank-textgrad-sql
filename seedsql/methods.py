"""The compared approaches.

Baselines: zero-shot, few-shot, error-retry, TextGrad (generic LLM loss).
Proposed:  vg_textgrad        - validation-guided TextGrad: the loss and a typed textual gradient are grounded in
                                the domain/temporal validator (static rules + metamorphic tests), see validator.py
Ablations: vg_textgrad_static - same, but the validator runs static rules only (no metamorphic tests)
           vg_retry           - validator findings fed straight back to the generator (no evaluator, no TextGrad)
In prompt-level mode (carry=True) vg_textgrad keeps an intent-conditioned RULE MEMORY: typed gradient bullets are
stored under their rule id, and a new question starts from the base prompt plus only the lessons whose rules
apply to that question's intent.

The four original approaches. `textgrad` here is a transparent re-implementation of TextGrad's
forward -> loss -> backward -> TGD-step loop (identical to the web demo). See textgrad_lib.py for the
same loop built on the official `textgrad` package."""
import re

from .db import extract_sql
from .intent import extract_intent, load_rules
from .prompts import (BASE_INSTRUCTIONS, generator_prompt, gradient_prompt, loss_prompt, retry_prompt,
                      step_prompt, vg_gradient_prompt, vg_loss_prompt, vg_retry_prompt)
from .validator import format_findings, validate

METHODS = ["zero", "few", "selfcorr", "textgrad", "vg_retry", "vg_textgrad_static", "vg_textgrad"]
LABELS = {"zero": "Zero-shot", "few": "Few-shot", "selfcorr": "Error-retry", "textgrad": "TextGrad",
          "textgrad_lib": "TextGrad (library)", "vg_retry": "Validator-retry", "vg_textgrad_static": "VG-TextGrad (static)",
          "vg_textgrad": "VG-TextGrad"}


def applicable_rules(intent):
    """Rule ids that apply to a question, from its intent (used by the rule memory)."""
    ids = {"JOIN-KEY", "DOM-DOUBLECOUNT", "SCHEMA"}
    ids |= {"TEMP-LATEST"} if intent.latest else set()
    ids |= {"TEMP-RANGE"} if (intent.years or intent.year_from or intent.year_before) else set()
    ids |= {"TEMP-NORETEST"} if intent.no_retest else set()
    ids |= {"DOM-THRESHOLD"} if intent.threshold is not None else set()
    ids |= {"DOM-STOCK"} if intent.stock else set()
    ids |= {"DOM-STORAGE"} if intent.storage_violation else set()
    ids |= {"AGG-GROUP"} if intent.group_each else set()
    ids |= {"AGG-COUNT"} if intent.count else set()
    return ids


class RuleMemory:
    """Intent-conditioned rule memory for prompt-level VG-TextGrad."""

    def __init__(self, per_rule=2):
        self.lessons, self.per_rule = {}, per_rule

    def add_from_gradient(self, gradient):
        for rid, text in re.findall(r"\[([A-Z]+-[A-Z]+|SCHEMA|EXEC)\]\s*(.+)", gradient or ""):
            lst = self.lessons.setdefault(rid, [])
            text = text.strip()
            if text not in lst:
                lst.append(text)
                del lst[:-self.per_rule]

    def prompt_for(self, question, base=BASE_INSTRUCTIONS):
        ids = applicable_rules(extract_intent(question))
        lines = [f"- {t}" for rid in sorted(ids) for t in self.lessons.get(rid, [])]
        return base + ("\nLessons learned on this database:\n" + "\n".join(lines) if lines else "")

    def as_dict(self):
        return dict(self.lessons)


def _passed(res, loss):
    return bool(res["ok"]) and re.search(r"VERDICT:\s*PASS", loss or "", re.I) is not None \
        and re.search(r"VERDICT:\s*FAIL", loss or "", re.I) is None


def run_method(method, question, llm, db, max_iters=4, initial_instructions=BASE_INSTRUCTIONS,
               carry=False, on_iter=None, memory=None):
    calls0 = llm.calls
    iters = []

    def push(it):
        iters.append(it)
        if on_iter:
            on_iter(it)

    def check(sql, res, mode, k):
        rep = validate(question, sql, db, res=res, mode=mode, seed=k)
        return rep, format_findings(rep)

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

    elif method == "vg_retry":
        sql = extract_sql(llm(generator_prompt(BASE_INSTRUCTIONS, question)))
        for k in range(1, max_iters + 1):
            res = db.run(sql)
            rep, ftxt = check(sql, res, "full", k)
            it = {"k": k, "prompt": BASE_INSTRUCTIONS if k == 1 else "(previous SQL + validator findings appended)",
                  "sql": sql, "res": res, "validation": rep.as_dict(), "loss": ftxt,
                  "verdict": "PASS" if (res["ok"] and rep.ok) else "FAIL"}
            push(it)
            if it["verdict"] == "PASS" or k == max_iters:
                break
            sql = extract_sql(llm(vg_retry_prompt(question, sql, ftxt)))

    elif method in ("vg_textgrad", "vg_textgrad_static"):
        mode = "static" if method.endswith("static") else "full"
        instructions = memory.prompt_for(question) if (carry and memory is not None) else initial_instructions
        for k in range(1, max_iters + 1):
            sql = extract_sql(llm(generator_prompt(instructions, question)))          # forward
            res = db.run(sql)                                                          # execute
            rep, ftxt = check(sql, res, mode, k)                                       # validate (gold-free)
            loss = llm(vg_loss_prompt(question, sql, res, ftxt))                       # grounded loss
            passed = _passed(res, loss) and rep.ok      # validator findings veto a PASS
            it = {"k": k, "prompt": instructions, "sql": sql, "res": res, "loss": loss,
                  "validation": rep.as_dict(), "verdict": "PASS" if passed else "FAIL"}
            if passed or k == max_iters:
                push(it)
                break
            it["gradient"] = llm(vg_gradient_prompt(instructions, question, sql, res, loss, ftxt, carry))  # typed gradient
            if carry and memory is not None:
                memory.add_from_gradient(it["gradient"])
            step = llm(step_prompt(instructions, it["gradient"], carry))                                  # TGD step
            m = re.search(r"<IMPROVED_VARIABLE>([\s\S]*?)</IMPROVED_VARIABLE>", step, re.I)
            it["new_prompt"] = (m.group(1) if m else step).strip()
            instructions = it["new_prompt"]
            push(it)
        return {"method": method, "iterations": iters, "final": iters[-1], "calls": llm.calls - calls0,
                "final_instructions": instructions, "memory": memory.as_dict() if memory else None}

    elif method == "textgrad_lib":
        from .textgrad_lib import run_textgrad_library
        return run_textgrad_library(question, llm, db, max_iters=max_iters,
                                    initial_instructions=initial_instructions, on_iter=on_iter)
    else:
        raise ValueError(method)

    return {"method": method, "iterations": iters, "final": iters[-1], "calls": llm.calls - calls0}
