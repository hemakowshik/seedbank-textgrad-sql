"""Semantic mutation operators for evaluating the validator offline.

Each operator injects one realistic Text-to-SQL mistake into a gold query. A mutant counts only if it
still executes AND returns a different result from the gold query on the benchmark database (so it is a
genuinely wrong query that execution feedback alone would accept). The validator never sees the gold
query; the gold is used here only to decide which mutants are wrong.
"""
import re

LATEST_RE = re.compile(r"\s*(AND\s+)?\w+\.test_date\s*=\s*\(SELECT MAX\((\w+)\.test_date\) FROM GerminationTest \2 WHERE \2\.lot_id = \w+\.lot_id\)(\s+AND)?", re.I)


def _drop_latest(sql):
    m = LATEST_RE.search(sql)
    if not m:
        return None
    rep = " AND" if (m.group(1) and m.group(3)) else ""
    out = sql[:m.start()] + rep + sql[m.end():]
    out = re.sub(r"WHERE\s+AND\s+", "WHERE ", out, flags=re.I)
    out = re.sub(r"WHERE\s*;", ";", out, flags=re.I)
    out = re.sub(r"WHERE\s+(GROUP|ORDER)", r"\1", out, flags=re.I)
    return out


OPERATORS = [
    # (id, category the mistake belongs to, function)
    ("drop-latest", "temporal", _drop_latest),
    ("global-latest", "temporal",          # MAX over the whole table instead of per lot: looks right statically
     lambda s: re.sub(r"(SELECT MAX\((\w+)\.test_date\) FROM GerminationTest \2) WHERE \2\.lot_id = \w+\.lot_id", r"\1", s, count=1)
     if re.search(r"SELECT MAX\((\w+)\.test_date\) FROM GerminationTest \1 WHERE", s) else None),
    ("earliest-not-latest", "temporal",
     lambda s: s.replace("SELECT MAX(g2.test_date)", "SELECT MIN(g2.test_date)", 1) if "SELECT MAX(g2.test_date)" in s else None),
    ("drop-no-retest", "temporal",
     lambda s: re.sub(r"\s+AND NOT EXISTS \(SELECT 1 FROM GerminationTest \w+ WHERE [^)]*\)", "", s, count=1) if "NOT EXISTS" in s else None),
    ("drop-date-bound", "temporal",
     lambda s: re.sub(r"\s*AND\s+\w*\.?(test_date|recorded_date|date)\s*<\s*'\d{4}-01-01'", "", s, count=1)
     if re.search(r"AND\s+\w*\.?(test_date|recorded_date|date)\s*<\s*'\d{4}-01-01'", s) else None),
    ("threshold-off-by-one", "domain",
     lambda s: re.sub(r"germination_rate\s*<\s*(\d+)", lambda m: f"germination_rate < {int(m.group(1)) + 5}", s, count=1)
     if re.search(r"germination_rate\s*<\s*\d+", s) else None),
    ("threshold-direction", "domain",
     lambda s: re.sub(r"germination_rate\s*>=\s*(\d+)", r"germination_rate <= \1", s, count=1) if re.search(r"germination_rate\s*>=\s*\d+", s) else None),
    ("drop-stock", "domain",
     lambda s: re.sub(r"\s+AND\s+\w*\.?quantity\s*>\s*0", "", s, count=1) if re.search(r"AND\s+\w*\.?quantity\s*>\s*0", s) else None),
    ("or-to-and", "domain",
     lambda s: re.sub(r"(temperature\s*>\s*[\d.]+)\s+OR\s+(\w*\.?humidity)", r"\1 AND \2", s, count=1) if re.search(r"temperature\s*>\s*[\d.]+\s+OR", s) else None),
    ("double-count-stock", "domain",
     lambda s: s.replace("l.quantity AS current_stock", "l.quantity - SUM(d.quantity) AS current_stock", 1)
     if "l.quantity AS current_stock" in s else (s.replace("l.quantity + SUM(d.quantity)", "l.quantity - SUM(d.quantity)", 1) if "l.quantity + SUM(d.quantity)" in s else None)),
    ("wrong-join-key", "join",
     lambda s: s.replace("v.variety_id = l.variety_id", "v.variety_id = l.lot_id", 1) if "v.variety_id = l.variety_id" in s else None),
    ("drop-group-by", "aggregation",
     lambda s: re.sub(r"\s+GROUP BY [^;]*?(?=( HAVING| ORDER| LIMIT|;))", "", s, count=1)
     if " GROUP BY " in s and " HAVING " not in s else None),
]


def mutants(gold_sql):
    for op_id, cat, fn in OPERATORS:
        try:
            m = fn(gold_sql)
        except Exception:
            m = None
        if m and m.strip() != gold_sql.strip():
            yield op_id, cat, m
