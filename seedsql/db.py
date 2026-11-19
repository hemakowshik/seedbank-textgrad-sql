"""Read-only SQL execution, SQL extraction, result matching (execution accuracy) and error categories.
Logic mirrors the web demo so both report comparable numbers."""
import os
import re
import sqlite3

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(_ROOT, "data", "seedbank.db")


class SeedBankDB:
    def __init__(self, path=DB_PATH, con=None):
        if con is not None:          # wrap an existing (e.g. in-memory, perturbed) connection
            self.con = con
            return
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} not found - run: python data/build_database.py")
        # read-only connection (safe execution)
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self.con.execute("PRAGMA query_only = ON")

    def clone(self):
        """Writable in-memory copy for controlled state changes (perturbation tests).
        Returns (writable_connection, SeedBankDB-wrapper). Call .freeze() before running model SQL."""
        mem = sqlite3.connect(":memory:", check_same_thread=False)
        self.con.backup(mem)
        return mem, SeedBankDB(con=mem)

    def freeze(self):
        self.con.execute("PRAGMA query_only = ON")

    def run(self, sql, max_rows=5000, timeout_s=10.0):
        s = (sql or "").strip()
        if not s:
            return {"ok": False, "error": "Empty query"}
        body = re.sub(r"^(\s*--[^\n]*\n)+", "", s)
        if not re.match(r"^\s*(with|select)\b", body, re.I):
            return {"ok": False, "error": "Only read-only SELECT/WITH queries are permitted."}
        import time
        deadline = time.time() + timeout_s
        self.con.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10000)
        try:
            cur = self.con.execute(s)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchmany(max_rows)]
            return {"ok": True, "columns": cols, "values": rows}
        except sqlite3.Warning as e:  # e.g. multiple statements
            return {"ok": False, "error": str(e)}
        except sqlite3.Error as e:
            msg = str(e)
            if "interrupted" in msg:
                msg = f"query timed out after {timeout_s:.0f}s (interrupted)"
            return {"ok": False, "error": msg}
        finally:
            self.con.set_progress_handler(None, 0)


def extract_sql(text):
    t = str(text or "")
    m = re.search(r"```(?:sql|sqlite)?\s*([\s\S]*?)```", t, re.I)
    if m:
        t = m.group(1)
    t = re.sub(r"^\s*(sql|query)\s*:\s*", "", t, flags=re.I).strip()
    m2 = re.search(r"\b(with|select)\b", t, re.I)
    if m2 and m2.start() > 0:
        t = t[m2.start():]
    return t.strip()


def _norm(v):
    if v is None:
        return "NULL"
    if isinstance(v, str):
        t = v.strip()
        try:
            v = float(t)
        except ValueError:
            return "s:" + t.lower()
    if isinstance(v, (int, float)):
        return "n:%.2f" % round(float(v), 2)
    return "s:" + str(v)


def results_match(gold, pred):
    """Relaxed execution accuracy: same row count, and every gold column is matched by a distinct
    predicted column such that the projected row multisets are equal. Ignores row order, column
    order, aliases and extra predicted columns. Numbers compared to 2 decimals."""
    if not gold or not gold.get("ok") or not pred or not pred.get("ok"):
        return False
    if len(gold["values"]) != len(pred["values"]):
        return False
    if not gold["values"]:
        return True
    gc, pc = len(gold["columns"]), len(pred["columns"])

    def col_sig(r, j):
        return "|".join(sorted(_norm(row[j]) for row in r["values"]))

    def tuples(r, cols):
        return sorted("§".join(_norm(row[j]) for j in cols) for row in r["values"])

    gs = [col_sig(gold, j) for j in range(gc)]
    ps = [col_sig(pred, j) for j in range(pc)]
    gold_t = tuples(gold, list(range(gc)))
    used, mapping = [False] * pc, []

    def bt(j):
        if j == gc:
            return tuples(pred, mapping) == gold_t
        for i in range(pc):
            if not used[i] and ps[i] == gs[j]:
                used[i] = True
                mapping.append(i)
                if bt(j + 1):
                    return True
                mapping.pop()
                used[i] = False
        return False

    return bt(0)


def error_category(res, correct=None):
    if res is None:
        return "No SQL"
    if not res["ok"]:
        e = res["error"].lower()
        if "only read-only" in e or "empty query" in e:
            return "Invalid / non-SELECT"
        if "syntax error" in e or "incomplete input" in e or "unrecognized token" in e:
            return "Syntax error"
        if "no such column" in e:
            return "Unknown column"
        if "no such table" in e:
            return "Unknown table"
        if "ambiguous column" in e:
            return "Ambiguous column"
        if "misuse of aggregate" in e or "group by" in e:
            return "Aggregation misuse"
        return "Other execution error"
    if correct is False:
        return "Wrong result (empty)" if not res["values"] else "Wrong result"
    return None
