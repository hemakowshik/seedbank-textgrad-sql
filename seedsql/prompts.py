"""Prompt templates. These are kept identical to the web demo (web/app.template.html)."""
import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(_ROOT, "data", "benchmark.json"), encoding="utf-8") as _f:
    BENCH = json.load(_f)

_DEFAULT_SCHEMA_TEXT = """SeedVariety(variety_id INTEGER PK, crop_name TEXT, local_name TEXT, crop_type TEXT, drought_tolerance TEXT)
  -- crop_type values: 'Millet','Cereal','Pulse','Vegetable','Oilseed'
  -- drought_tolerance values: 'High','Medium','Low'
SeedLot(lot_id INTEGER PK, variety_id INTEGER FK->SeedVariety.variety_id, storage_location TEXT, quantity INTEGER, collection_date TEXT)
  -- storage_location values: 'Cold Room A','Cold Room B','Clay Pot Store','Ambient Shelf','Village Hub - Mandya'
  -- quantity = grams currently in stock (0 means exhausted)
GerminationTest(test_id INTEGER PK, lot_id INTEGER FK->SeedLot.lot_id, test_date TEXT, germination_rate REAL)
  -- germination_rate is a percentage 0-100; a lot can have several tests over time
StorageLog(log_id INTEGER PK, lot_id INTEGER FK->SeedLot.lot_id, recorded_date TEXT, temperature REAL, humidity REAL)
  -- monthly readings; temperature in deg C, humidity in % relative humidity
Distribution(distribution_id INTEGER PK, lot_id INTEGER FK->SeedLot.lot_id, destination TEXT, quantity INTEGER, date TEXT)
  -- seed given out to farmer groups; quantity in grams
Notes: all dates are TEXT 'YYYY-MM-DD'. The database engine is SQLite. Today's date is 2026-11-01."""
# The real-data builder writes an exact schema description into benchmark.json
SCHEMA_TEXT = BENCH.get("schema_text") or _DEFAULT_SCHEMA_TEXT

BASE_INSTRUCTIONS = ("You are an expert assistant that translates questions about a community seed-bank "
                     "database into a single correct SQLite query. Use only the tables and columns in the "
                     "schema. Return only the SQL query.")


def generator_prompt(instructions, question, few_shot=False):
    p = f"{instructions}\n\n### Database schema (SQLite)\n{SCHEMA_TEXT}\n"
    if few_shot:
        p += "\n### Examples\n" + "\n\n".join(
            f"Question: {e['question']}\nSQL: {e['sql']}" for e in BENCH["few_shot_examples"]) + "\n"
    p += f"\n### Question\n{question}\n\nRespond with only the SQL query inside a ```sql code block."
    return p


def _fmt(v):
    if isinstance(v, float) and not v.is_integer():
        return round(v, 2)
    return "NULL" if v is None else v


def feedback_text(res):
    if res is None:
        return "No SQL was produced."
    if not res["ok"]:
        return f"status: ERROR\nerror message: {res['error']}"
    head = "\n".join(" | ".join(str(_fmt(v)) for v in row) for row in res["values"][:8])
    return (f"status: executed successfully\ncolumns: {', '.join(res['columns'])}\n"
            f"row count: {len(res['values'])}\nfirst rows:\n{head or '(no rows)'}")


LOSS_INSTRUCTION = """You are a strict reviewer of SQL queries written by a Text-to-SQL system for a community seed-bank database. You do NOT have a reference answer; judge using the question, the schema, the SQL and the execution feedback.
Check: (1) it executes; (2) correct tables and join keys; (3) every condition in the question is applied with the exact stored values, thresholds and date ranges; (4) aggregation, GROUP BY and HAVING are correct; (5) "most recent / latest" logic is computed per lot where required; (6) the returned columns are what the question asks for; (7) the result is plausible (an empty result often signals a wrong filter value).
List concrete problems as short bullets, or write "No problems found."
The final line must be exactly "VERDICT: PASS" or "VERDICT: FAIL"."""


def loss_prompt(question, sql, res):
    return f"""You are a strict reviewer of SQL queries written by a Text-to-SQL system for a community seed-bank database. You do NOT have a reference answer; judge using the question, the schema, the SQL and the execution feedback.

<SCHEMA>
{SCHEMA_TEXT}
</SCHEMA>

<QUESTION>
{question}
</QUESTION>

<SQL>
{sql}
</SQL>

<EXECUTION_FEEDBACK>
{feedback_text(res)}
</EXECUTION_FEEDBACK>

Check: (1) it executes; (2) correct tables and join keys; (3) every condition in the question is applied with the exact stored values, thresholds and date ranges; (4) aggregation, GROUP BY and HAVING are correct; (5) "most recent / latest" logic is computed per lot where required; (6) the returned columns are what the question asks for; (7) the result is plausible (an empty result often signals a wrong filter value).
List concrete problems as short bullets, or write "No problems found."
The final line must be exactly "VERDICT: PASS" or "VERDICT: FAIL"."""


def gradient_prompt(instructions, question, sql, res, loss):
    return f"""You are part of an optimization system that improves a text variable by computing textual gradients: precise, critical feedback about how the variable should change.

The variable is the SYSTEM PROMPT given to a language model that writes SQLite queries for a seed-bank database.
<VARIABLE>
{instructions}
</VARIABLE>

It was used in this computation:
<QUESTION>
{question}
</QUESTION>
<GENERATED_SQL>
{sql}
</GENERATED_SQL>
<EXECUTION_FEEDBACK>
{feedback_text(res)}
</EXECUTION_FEEDBACK>

The evaluator (loss function) produced this critique:
<LOSS>
{loss}
</LOSS>

Explain how the VARIABLE should be changed so that the model writes a correct query next time. Be specific and actionable: you may name tables, join keys, filter values and SQL patterns the prompt should emphasise. Do not rewrite the variable yourself; give the feedback only, as at most 6 bullets."""


def step_prompt(instructions, gradient, carry=False):
    scope = ("The improved prompt will be reused for OTHER questions about the same database, so express the "
             "lessons as general, reusable rules. Do not mention this particular question."
             if carry else
             "The improved prompt will be used again for the same question, so it may include guidance "
             "specific to this question.")
    return f"""You are part of an optimization system that improves text (a variable) using textual gradient descent.

Variable role: system prompt for a Text-to-SQL language model working on a community seed-bank SQLite database.
<VARIABLE>
{instructions}
</VARIABLE>

Feedback (gradient) on the variable:
<FEEDBACK>
{gradient}
</FEEDBACK>

{scope}
Keep everything in the current variable that is still useful, address the feedback, and keep it under 250 words. Do not include the database schema; it is supplied separately.
Respond with the improved variable only, between <IMPROVED_VARIABLE> and </IMPROVED_VARIABLE>."""


def retry_prompt(question, prev_sql, res):
    return (generator_prompt(BASE_INSTRUCTIONS, question, False) +
            f"\n\nYour previous query was:\n```sql\n{prev_sql}\n```\n"
            f"It failed with this SQLite error: {res['error'] if res else 'no SQL produced'}\nWrite a corrected query.")
