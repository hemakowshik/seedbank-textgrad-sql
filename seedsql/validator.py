"""Domain-aware temporal validator for seed-bank SQL (gold-free).

Given the question, the predicted SQL and the database, it returns structured findings:
    Finding(rule, category, evidence, fix, source)
with category in {execution, schema, join, temporal, domain, aggregation}.

Two kinds of evidence, neither of which uses the gold query:

1. Static rule checks (source='static'): the SQL text is checked against the configurable rules in
   data/domain_rules.json, conditioned on the question's intent (seedsql/intent.py). Example: the
   question says "most recent germination" but the SQL never selects the latest test per lot.

2. Intent-conditioned metamorphic tests (source='metamorphic'): the database is copied into memory,
   changed in a controlled way, and the predicted SQL is re-run. The expected change in its output
   follows from the question's intent alone. Example: for "lots whose most recent germination is below
   75%", adding a NEWER passing test (90%) to a returned lot must remove that lot from the answer; if it
   does not, the query ignores the latest-record semantics. These tests catch semantic errors in queries
   that execute successfully and look plausible, which execution feedback cannot detect.
"""
import random
import re
from dataclasses import asdict, dataclass

from .intent import extract_intent, load_rules

REF_DATE = "2026-11-01"
CATEGORIES = ("execution", "schema", "join", "temporal", "domain", "aggregation")


@dataclass
class Finding:
    rule: str
    category: str
    evidence: str
    fix: str
    source: str  # 'execution' | 'static' | 'metamorphic'

    def as_dict(self):
        return asdict(self)


@dataclass
class Report:
    findings: list
    intent: dict
    tests_run: int
    tests_failed: int

    @property
    def ok(self):
        return not self.findings

    def categories(self):
        return sorted({f.category for f in self.findings})

    def as_dict(self):
        return {"findings": [f.as_dict() for f in self.findings], "intent": self.intent,
                "tests_run": self.tests_run, "tests_failed": self.tests_failed}


# ----------------------------------------------------------------------------------- helpers
def _norm(sql):
    s = re.sub(r"--[^\n]*", " ", sql or "")
    s = re.sub(r"/\*.*?\*/", " ", s, flags=re.S)
    return re.sub(r"\s+", " ", s).strip().lower()


def _strip_subqueries(s):
    """Remove '(select ...)' blocks so that aggregates inside subqueries are ignored."""
    out, i = [], 0
    while i < len(s):
        if s[i] == "(" and re.match(r"\(\s*select\b", s[i:]):
            depth = 0
            while i < len(s):
                depth += s[i] == "("
                depth -= s[i] == ")"
                i += 1
                if depth == 0:
                    break
            out.append(" (subq) ")
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


_TABLES = {"seedvariety", "seedlot", "germinationtest", "storagelog", "distribution"}
_KW = {"on", "where", "join", "left", "right", "inner", "outer", "cross", "group", "order", "limit", "using",
       "natural", "union", "having", "as", "and", "or", "select", "from", "full"}


def _subqueries(s):
    """All '(select ...)' blocks, outermost first."""
    out = []
    for m in re.finditer(r"\(\s*select\b", s):
        i, depth = m.start(), 0
        for j in range(i, len(s)):
            depth += s[j] == "("
            depth -= s[j] == ")"
            if depth == 0:
                out.append(s[i:j + 1])
                break
    return out


def _aliases(s):
    amap = {}
    for m in re.finditer(r"\b(from|join)\s+(\w+)(?:\s+(?:as\s+)?(\w+))?", s):
        t = m.group(2)
        if t in _TABLES:
            amap[t] = t
            if m.group(3) and m.group(3) not in _KW:
                amap[m.group(3)] = t
    return amap


def _allowed_pairs(rules):
    pairs = set()
    for a, b in rules["schema"]["join_keys"]:
        ta, ca = a.lower().split(".")
        tb, cb = b.lower().split(".")
        pairs.add(frozenset([(ta, ca), (tb, cb)]))
    return pairs


def _entity_values(res, entity, db):
    """Return (column index, set of entity keys) for the answer entity, or (None, None)."""
    if not res or not res.get("ok") or not res["columns"]:
        return None, None
    cols = [c.lower() for c in res["columns"]]
    if entity == "lot":
        for i, c in enumerate(cols):
            if c == "lot_id" or c.endswith("lot_id") or c == "lot":
                return i, {row[i] for row in res["values"]}
    if entity == "variety":
        names = {r[0] for r in db.con.execute("SELECT local_name FROM SeedVariety")}
        ids = {r[0] for r in db.con.execute("SELECT variety_id FROM SeedVariety")}
        for i, c in enumerate(cols):
            vals = {row[i] for row in res["values"]}
            if vals and vals <= names:
                return i, vals
            if c in ("variety_id",) and vals <= ids:
                return i, vals
    return None, None


def _lots_of(con, entity, key):
    if entity == "lot":
        return [key]
    if isinstance(key, int):
        return [r[0] for r in con.execute("SELECT lot_id FROM SeedLot WHERE variety_id = ?", (key,))]
    return [r[0] for r in con.execute(
        "SELECT l.lot_id FROM SeedLot l JOIN SeedVariety v ON v.variety_id = l.variety_id WHERE v.local_name = ?", (key,))]


# ----------------------------------------------------------------------------------- static rules
def static_checks(question, sql, res, intent, rules):
    f = []
    fb = {r["id"]: r["feedback"] for r in rules["rules"]}
    s = _norm(sql)
    if res is not None and not res.get("ok"):
        err = res.get("error", "")
        cat = "schema" if ("no such column" in err or "no such table" in err) else "execution"
        f.append(Finding("SCHEMA" if cat == "schema" else "EXEC", cat, f"SQLite error: {err}",
                         fb["SCHEMA"] if cat == "schema" else "Fix the SQL so that it executes.", "execution"))

    has_latest = bool(re.search(r"max\s*\(\s*(\w+\.)?test_date\s*\)", s) or "row_number" in s or
                      re.search(r"\brank\s*\(", s) or re.search(r"order by [\w.]*test_date desc", s) or
                      re.search(r"not exists\s*\(\s*select[^)]*test_date\s*>\s*[\w.]*test_date", s))
    if intent.latest and not has_latest:
        f.append(Finding("TEMP-LATEST", "temporal",
                         "The question refers to the most recent germination result, but the SQL never selects the latest test per lot.",
                         fb["TEMP-LATEST"], "static"))
    # the latest-test subquery must be per lot (correlated or grouped), not the newest test in the whole table
    if intent.latest and has_latest and not ("row_number" in s or re.search(r"\brank\s*\(", s)):
        latest_subs = [q for q in _subqueries(s) if re.search(r"max\s*\(\s*(\w+\.)?test_date\s*\)|order by [\w.]*test_date desc", q)]
        uncorrelated = [q for q in latest_subs if not re.search(r"\bwhere\b[^()]*lot_id\s*=", q) and "group by" not in q]
        grouped = re.search(r"group by\s+[\w.]*lot_id", s) or re.search(r"partition by\s+[\w.]*lot_id", s)
        if latest_subs and uncorrelated and not grouped:
            f.append(Finding("TEMP-PERLOT", "temporal",
                             "The SQL takes MAX(test_date) over the whole GerminationTest table, i.e. the single newest test in the database, not the latest test of each lot.",
                             fb["TEMP-PERLOT"], "static"))
    if intent.no_retest and not ("not exists" in s or "max(" in s.replace(" ", "")):
        f.append(Finding("TEMP-NORETEST", "temporal",
                         "The question requires that no later retest exists, but the SQL does not compare against later tests.",
                         fb["TEMP-NORETEST"], "static"))
    for y in sorted(set(intent.years)):
        if str(y) not in s and not (intent.year_from == y or intent.year_before == y):
            f.append(Finding("TEMP-RANGE", "temporal", f"The question restricts the period to {y}, but '{y}' does not appear in the SQL.",
                             fb["TEMP-RANGE"], "static"))
    for y in sorted(set(intent.in_years)):
        bounded = (re.search(rf"'{y + 1}-01-01'|'{y}-12-31", s) or re.search(rf"strftime\s*\(\s*'%y'[^)]*\)\s*=\s*'{y}'", s)
                   or re.search(rf"like\s*'{y}", s) or re.search(rf"substr\s*\([^)]*\)\s*=\s*'{y}'", s)
                   or re.search(rf"between\s*'{y}", s))
        if str(y) in s and not bounded:
            f.append(Finding("TEMP-RANGE", "temporal", f"The question restricts the period to the year {y}, but the SQL has no upper bound for {y} (records from later years are included).",
                             fb["TEMP-RANGE"], "static"))
    for y, word in ((intent.year_from, "from"), (intent.year_before, "before")):
        if y and str(y) not in s and not (word == "before" and f"'{y - 1}-12-31" in s):
            f.append(Finding("TEMP-RANGE", "temporal", f"The question says '{word} {y}', but '{y}' does not appear in the SQL.",
                             fb["TEMP-RANGE"], "static"))

    if intent.threshold is not None:
        comps = re.findall(r"germination_rate\s*(<=|>=|<>|!=|<|>|=)\s*(\d+(?:\.\d+)?)", s)
        comps += re.findall(r"select\s+[\w.]*germination_rate\b[^()]*\)\s*(<=|>=|<>|!=|<|>|=)\s*(\d+(?:\.\d+)?)", s)
        comps += [({"<": ">", ">": "<", "<=": ">=", ">=": "<="}.get(op, op), v)
                  for v, op in re.findall(r"(\d+(?:\.\d+)?)\s*(<=|>=|<|>)\s*[\w.]*germination_rate", s)]
        vals = [(op, float(v)) for op, v in comps]
        same = [op for op, v in vals if abs(v - intent.threshold) < 1e-9]
        if not same:
            f.append(Finding("DOM-THRESHOLD", "domain",
                             f"The question uses a germination threshold of {intent.threshold:g}%, but the SQL does not compare germination_rate with {intent.threshold:g}.",
                             fb["DOM-THRESHOLD"], "static"))
        elif intent.threshold_op not in same:
            f.append(Finding("DOM-THRESHOLD", "domain",
                             f"The question needs germination_rate {intent.threshold_op} {intent.threshold:g}, but the SQL uses '{same[0]}'.",
                             fb["DOM-THRESHOLD"], "static"))
    sums_stock = bool(re.search(r"sum\s*\(\s*[\w.]*quantity\s*\)", s)) and "total" in question.lower() and intent.entity not in ("lot", "variety")
    if intent.stock and not sums_stock and not re.search(r"quantity\s*(>\s*0(?![\d.])|>=\s*1\b|<>\s*0|!=\s*0)", s):
        f.append(Finding("DOM-STOCK", "domain", "The question asks for available stock, but the SQL does not require quantity > 0.",
                         fb["DOM-STOCK"], "static"))
    if re.search(r"quantity\s*-\s*\(?\s*(select\s+)?(coalesce\s*\(\s*)?(sum|total)\s*\(", s) or \
            re.search(r"\w+\.quantity\s*-\s*\w+\.quantity", s):
        f.append(Finding("DOM-DOUBLECOUNT", "domain",
                         "The SQL subtracts distributed quantities from SeedLot.quantity, which is already the stock after distributions.",
                         fb["DOM-DOUBLECOUNT"], "static"))
    if intent.storage_violation:
        if re.search(r"temperature\s*>=?\s*[\d.]+\s+and\s+[\w.]*humidity", s) or \
                re.search(r"humidity\s*>=?\s*[\d.]+\s+and\s+[\w.]*temperature", s):
            f.append(Finding("DOM-STORAGE", "domain",
                             "Out-of-range storage means temperature OR humidity above its limit; the SQL requires both (AND).",
                             fb["DOM-STORAGE"], "static"))
        for lim, col in ((intent.temp_limit, "temperature"), (intent.hum_limit, "humidity")):
            if lim is not None and not re.search(rf"{col}\s*\)?\s*>=?\s*{lim:g}(?![\d])", s):
                f.append(Finding("DOM-STORAGE", "domain", f"The SQL does not compare {col} with the stated limit {lim:g}.",
                                 fb["DOM-STORAGE"], "static"))

    amap, allowed = _aliases(s), _allowed_pairs(rules)
    for a1, c1, a2, c2 in re.findall(r"\b(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)", s):
        t1, t2 = amap.get(a1), amap.get(a2)
        if not t1 or not t2 or t1 == t2:
            continue
        key_cols = {"lot_id", "variety_id"}
        if c1 in key_cols and c2 in key_cols:
            ok = frozenset([(t1, c1), (t2, c2)]) in allowed or (c1 == c2 == "lot_id" and "seedvariety" not in (t1, t2))
            if not ok:
                f.append(Finding("JOIN-KEY", "join", f"Join condition {a1}.{c1} = {a2}.{c2} links {t1} to {t2} on the wrong key.",
                                 fb["JOIN-KEY"], "static"))
    outer = _strip_subqueries(s)
    has_agg = bool(re.search(r"\b(count|sum|avg|min|max)\s*\(", outer))
    if intent.group_each and has_agg and "group by" not in outer:
        f.append(Finding("AGG-GROUP", "aggregation", "The question asks for a result for each group, but the outer query aggregates without GROUP BY.",
                         fb["AGG-GROUP"], "static"))
    sel = re.search(r"^\s*select\s+(distinct\s+)?(.*?)\s+from\s", outer)
    if sel and "group by" not in outer:
        items, depth, cur = [], 0, ""
        for ch in sel.group(2):
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                items.append(cur); cur = ""
            else:
                cur += ch
        items.append(cur)
        agg = [i for i in items if re.search(r"\b(count|sum|avg|min|max|total|group_concat)\s*\(", i)]
        plain = [i for i in items if i not in agg and re.search(r"[a-z_]", re.sub(r"\bas\s+\w+", "", i)) and "(subq)" not in i]
        # SQLite documents that a bare column next to a single min()/max() comes from the min/max row
        single_minmax = len(agg) == 1 and re.search(r"\b(min|max)\s*\(", agg[0]) and not re.search(r"\b(count|sum|avg)\s*\(", agg[0])
        if agg and plain and not single_minmax:
            f.append(Finding("AGG-BARE", "aggregation",
                             f"The SELECT list mixes aggregates ({agg[0].strip()}) with plain columns ({plain[0].strip()}) without GROUP BY; SQLite returns one arbitrary row.",
                             fb["AGG-BARE"], "static"))
    if intent.count and "count(" not in s.replace(" ", "") and "sum(case" not in s.replace(" ", "") and not intent.group_each:
        f.append(Finding("AGG-COUNT", "aggregation", "The question asks 'how many', but the SQL does not count.",
                         fb["AGG-COUNT"], "static"))
    return f


# ----------------------------------------------------------------------------------- metamorphic tests
def metamorphic_checks(question, sql, res, intent, db, rules, rng):
    """Returns (findings, tests_run). Each test: copy DB -> controlled change -> re-run SQL -> expected change."""
    if not res or not res.get("ok"):
        return [], 0
    margin = rules["metamorphic"]["margin"]
    limit = rules["metamorphic"]["max_tests_per_query"]
    fb = {r["id"]: r["feedback"] for r in rules["rules"]}
    entity = intent.entity
    col, present = _entity_values(res, entity, db) if entity in ("lot", "variety") else (None, None)
    s = _norm(sql)
    has_limit = " limit " in f" {s} "
    findings, tests = [], 0

    def rerun(mutate):
        mem, wrapped = db.clone()
        mutate(mem)
        mem.commit()
        wrapped.freeze()
        out = wrapped.run(sql)
        mem.close()
        return out

    def keys(r):
        if not r.get("ok") or col is None or col >= len(r["columns"]):
            return None
        return {row[col] for row in r["values"]}

    def add_test(con, lot, rate):
        con.execute("INSERT INTO GerminationTest (lot_id, test_date, germination_rate) VALUES (?, ?, ?)", (lot, REF_DATE, rate))

    sample = sorted(present, key=str) if present else []
    rng.shuffle(sample)
    T = intent.threshold

    # MR-LATEST: a newer test that flips the threshold must flip membership of the entity
    if intent.latest and T is not None and col is not None and sample and not has_limit:
        for key in sample[:2]:
            if tests >= limit:
                break
            new_rate = min(99.0, T + margin) if intent.threshold_op in ("<", "<=") else max(1.0, T - margin)
            out = rerun(lambda con: [add_test(con, l, new_rate) for l in _lots_of(con, entity, key)])
            tests += 1
            after = keys(out)
            if after is not None and key in after:
                findings.append(Finding("TEMP-LATEST", "temporal",
                    f"Metamorphic test: after adding a newer germination test of {new_rate:g}% for every lot of {entity} '{key}', "
                    f"the query still returned '{key}'. The answer should depend only on the latest test.",
                    fb["TEMP-LATEST"], "metamorphic"))
                break
    # MR-LATEST-ADD (single-condition questions only): a newer failing test must ADD a lot
    # only when the answer depends on germination tests alone (no joins that could add other filters)
    single = not (intent.stock or intent.drought or intent.years or intent.year_from or intent.storage_violation) \
        and not re.search(r"\b(seedlot|seedvariety|storagelog|distribution)\b", s) and " in (" not in s
    if intent.latest and T is not None and entity == "lot" and col is not None and single and not has_limit \
            and intent.threshold_op in ("<", "<=") and tests < limit:
        cand = [r[0] for r in db.con.execute(
            "SELECT g.lot_id FROM GerminationTest g WHERE g.test_date = (SELECT MAX(test_date) FROM GerminationTest x "
            "WHERE x.lot_id = g.lot_id) AND g.germination_rate >= ?", (T + 1,)) if r[0] not in (present or set())]
        if cand:
            lot = rng.choice(sorted(cand))
            out = rerun(lambda con: add_test(con, lot, max(1.0, T - margin)))
            tests += 1
            after = keys(out)
            if after is not None and lot not in after:
                findings.append(Finding("TEMP-LATEST", "temporal",
                    f"Metamorphic test: lot {lot} passed its earlier tests; after adding a newer test of {max(1.0, T - margin):g}% "
                    f"(below {T:g}%) the query did not return it.", fb["TEMP-LATEST"], "metamorphic"))
    # MR-STOCK: zero stock must remove the entity
    if intent.stock and col is not None and sample and not has_limit and tests < limit:
        key = sample[-1]
        out = rerun(lambda con: [con.execute("UPDATE SeedLot SET quantity = 0 WHERE lot_id = ?", (l,))
                                 for l in _lots_of(con, entity, key)])
        tests += 1
        after = keys(out)
        if after is not None and key in after:
            findings.append(Finding("DOM-STOCK", "domain",
                f"Metamorphic test: after setting the stock of every lot of {entity} '{key}' to 0, the query still returned it.",
                fb["DOM-STOCK"], "metamorphic"))
    # MR-NORETEST: a later passing retest must remove the entity
    if intent.no_retest and col is not None and sample and tests < limit:
        key = sample[0]
        rate = min(99.0, (T or 75) + margin)
        out = rerun(lambda con: [add_test(con, l, rate) for l in _lots_of(con, entity, key)])
        tests += 1
        after = keys(out)
        if after is not None and key in after:
            findings.append(Finding("TEMP-NORETEST", "temporal",
                f"Metamorphic test: after recording a later retest ({rate:g}%) for '{key}', the query still returned it.",
                fb["TEMP-NORETEST"], "metamorphic"))
    # MR-RANGE: a record outside the stated period must not change the answer
    if intent.germination and intent.years and not intent.latest and tests < limit:
        y = min(intent.years) - 1
        lot = db.con.execute("SELECT lot_id FROM SeedLot ORDER BY lot_id LIMIT 1").fetchone()[0]
        out = rerun(lambda con: con.execute("INSERT INTO GerminationTest (lot_id, test_date, germination_rate) VALUES (?, ?, ?)",
                                            (lot, f"{y}-06-15", 30.0)))
        tests += 1
        if out.get("ok") and sorted(map(str, out["values"])) != sorted(map(str, res["values"])):
            findings.append(Finding("TEMP-RANGE", "temporal",
                f"Metamorphic test: adding a test dated {y}-06-15 (outside the period in the question) changed the answer.",
                fb["TEMP-RANGE"], "metamorphic"))
    # MR-STORAGE-OR: a reading above the temperature limit but within humidity must count as out of range
    counts_rows = "count(" in _strip_subqueries(s).replace(" ", "")
    if intent.storage_violation and entity == "lot" and col is not None and sample and counts_rows and tests < limit:
        num = next((i for i, c in enumerate(res["columns"]) if i != col and all(isinstance(r[i], (int, float)) for r in res["values"])), None)
        if num is not None:
            key = sample[0]
            before = next(r[num] for r in res["values"] if r[col] == key)
            tl, hl = intent.temp_limit or 15, intent.hum_limit or 50
            out = rerun(lambda con: con.execute("INSERT INTO StorageLog (lot_id, recorded_date, temperature, humidity) VALUES (?, ?, ?, ?)",
                                                (key, REF_DATE, tl + 5, hl - 10)))
            tests += 1
            if out.get("ok"):
                row = next((r for r in out["values"] if r[col] == key), None)
                if row is not None and row[num] == before:
                    findings.append(Finding("DOM-STORAGE", "domain",
                        f"Metamorphic test: a new reading for lot {key} at {tl + 5:g} C and {hl - 10:g}% humidity (temperature out of range) "
                        f"did not change its count; out-of-range must be temperature OR humidity.", fb["DOM-STORAGE"], "metamorphic"))
    return findings, tests


# ----------------------------------------------------------------------------------- entry point
def validate(question, sql, db, res=None, mode="full", seed=0, rules=None):
    """mode: 'full' (static + metamorphic) | 'static' (rules only)."""
    rules = rules or load_rules()
    intent = extract_intent(question, rules)
    res = res if res is not None else db.run(sql)
    findings = static_checks(question, sql, res, intent, rules)
    tests = 0
    if mode == "full":
        mf, tests = metamorphic_checks(question, sql, res, intent, db, rules, random.Random(seed))
        seen = {(x.rule, x.source) for x in findings}
        findings += [x for x in mf if (x.rule, x.source) not in seen]
    failed = sum(1 for x in findings if x.source == "metamorphic")
    return Report(findings=findings, intent=intent.as_dict(), tests_run=tests, tests_failed=failed)


def format_findings(report):
    if not report.findings:
        return "No rule violations found and all metamorphic tests passed." if report.tests_run else "No rule violations found."
    lines = []
    for i, f in enumerate(report.findings, 1):
        lines.append(f"{i}. [{f.category.upper()} / {f.rule} / {f.source}] {f.evidence}\n   Suggested correction: {f.fix}")
    return "\n".join(lines)
