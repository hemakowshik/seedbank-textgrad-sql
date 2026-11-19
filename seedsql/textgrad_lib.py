"""TextGrad loop built on the official `textgrad` package (pip install textgrad).

    system_prompt = tg.Variable(..., requires_grad=True)          # the optimised variable
    sql_var       = tg.BlackboxLLM(engine, system_prompt)(question)  # forward
    loss          = FormattedLLMCall(evaluator)(question, sql_var, execution_feedback)   # textual loss
    loss.backward(); optimizer.step()                              # gradients + TGD update

Execution feedback from SQLite enters the graph as a constant Variable, so the gradient flows from
the loss -> SQL answer -> system prompt.

Status: EXPERIMENTAL. This adapter has not been run end to end in this project, so no result in the
paper comes from it. All reported TextGrad numbers use the re-implementation in methods.py.

Notes
- Tested against the textgrad 0.1.x API (Variable, BlackboxLLM, TGD, autograd.FormattedLLMCall,
  engine.local_model_openai_api.ChatExternalClient). If your installed version differs, run the
  same experiment with `--methods textgrad` (the transparent re-implementation in methods.py).
- The engine is any OpenAI-compatible endpoint, configured from the same --provider/--model flags.
"""
import re

from .db import extract_sql
from .prompts import BASE_INSTRUCTIONS, LOSS_INSTRUCTION, SCHEMA_TEXT, feedback_text

_ENGINES = {}


def _engine(llm):
    key = (llm.provider, llm.model)
    if key in _ENGINES:
        return _ENGINES[key]
    try:
        import textgrad as tg  # noqa: F401
        from openai import OpenAI
        from textgrad.engine.local_model_openai_api import ChatExternalClient
    except ImportError as e:
        raise RuntimeError("method 'textgrad_lib' needs: pip install textgrad openai") from e
    client = OpenAI(base_url=llm.base_url, api_key=llm.api_key)
    eng = ChatExternalClient(client=client, model_string=llm.model)
    _ENGINES[key] = eng
    return eng


def run_textgrad_library(question, llm, db, max_iters=4, initial_instructions=BASE_INSTRUCTIONS, on_iter=None):
    import textgrad as tg
    from textgrad.autograd import FormattedLLMCall

    if llm.provider == "mock":
        raise RuntimeError("textgrad_lib cannot run with the mock provider")
    engine = _engine(llm)
    tg.set_backward_engine(engine, override=True)

    system_prompt = tg.Variable(initial_instructions, requires_grad=True,
                                role_description="system prompt to a Text-to-SQL language model for a "
                                                 "community seed-bank SQLite database")
    model = tg.BlackboxLLM(engine, system_prompt=system_prompt)
    optimizer = tg.TGD(parameters=[system_prompt])

    user_text = (f"### Database schema (SQLite)\n{SCHEMA_TEXT}\n\n### Question\n{question}\n\n"
                 "Respond with only the SQL query inside a ```sql code block.")
    q_var = tg.Variable(user_text, requires_grad=False, role_description="database schema and user question")

    fmt = ("<QUESTION>\n{question}\n</QUESTION>\n\n<SQL>\n{sql}\n</SQL>\n\n"
           "<EXECUTION_FEEDBACK>\n{feedback}\n</EXECUTION_FEEDBACK>")
    evaluator = FormattedLLMCall(engine=engine, format_string=fmt,
                                 fields={"question": None, "sql": None, "feedback": None},
                                 system_prompt=tg.Variable(LOSS_INSTRUCTION + "\n\nSchema:\n" + SCHEMA_TEXT,
                                                           requires_grad=False,
                                                           role_description="evaluator system prompt"))
    iters = []
    calls_est = 0
    for k in range(1, max_iters + 1):
        optimizer.zero_grad()
        prompt_before = system_prompt.value
        answer = model(q_var)
        answer.set_role_description("SQLite query that answers the question")
        sql = extract_sql(answer.value)
        res = db.run(sql)
        fb = tg.Variable(feedback_text(res), requires_grad=False,
                         role_description="result of executing the SQL on the database")
        qv = tg.Variable(question, requires_grad=False, role_description="user question")
        loss = evaluator(inputs={"question": qv, "sql": answer, "feedback": fb},
                         response_role_description="evaluation of the SQL query")
        calls_est += 2
        passed = res["ok"] and re.search(r"VERDICT:\s*PASS", loss.value, re.I) and \
            not re.search(r"VERDICT:\s*FAIL", loss.value, re.I)
        it = {"k": k, "prompt": prompt_before, "sql": sql, "res": res, "loss": loss.value,
              "verdict": "PASS" if passed else "FAIL"}
        if passed or k == max_iters:
            iters.append(it)
            if on_iter:
                on_iter(it)
            break
        loss.backward()
        optimizer.step()
        calls_est += 3  # backward through 2 nodes + optimizer
        it["gradient"] = "\n".join(g.value for g in system_prompt.gradients) if system_prompt.gradients else None
        it["new_prompt"] = system_prompt.value
        iters.append(it)
        if on_iter:
            on_iter(it)
    return {"method": "textgrad_lib", "iterations": iters, "final": iters[-1], "calls": calls_est,
            "final_instructions": system_prompt.value}
