"""Deterministic question-intent extraction for seed-bank questions.

The validator needs to know what a CORRECT query must do without seeing the gold answer. We derive
that from the question text alone, using the configurable phrase lists in data/domain_rules.json:
temporal scope (latest test, date range, no-retest), domain conditions (germination threshold and
direction, stock, storage limits), the answer entity (lot, variety, location, destination) and the
aggregation asked for. No LLM is used, so the intent is reproducible and cannot leak gold information.
"""
import json
import os
import re
from dataclasses import asdict, dataclass, field

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(_ROOT, "data", "domain_rules.json")


def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Intent:
    latest: bool = False                 # "most recent / latest" germination test per lot
    no_retest: bool = False              # result must have no later test on the same lot
    threshold: float = None              # germination threshold stated in the question (%)
    threshold_op: str = None             # '<', '>=', '>' or '<='
    germination: bool = False            # question is about germination results
    stock: bool = False                  # only lots with quantity > 0
    out_of_stock: bool = False           # lots with quantity = 0
    years: list = field(default_factory=list)          # years mentioned, e.g. [2026]
    in_years: list = field(default_factory=list)       # "in 2026" = the whole calendar year (needs both bounds)
    year_from: int = None                # "in 2025 or later", "since 2025"
    year_before: int = None              # "before 2018"
    storage_violation: bool = False
    temp_limit: float = None
    hum_limit: float = None
    entity: str = None                   # 'lot', 'variety', 'location', 'destination', 'crop_type', None
    group_each: bool = False
    count: bool = False
    drought: str = None                  # 'High' / 'Medium' / 'Low'

    def as_dict(self):
        return {k: v for k, v in asdict(self).items() if v not in (None, False, [])}


def _has(text, phrases):
    return any(p in text for p in phrases)


def extract_intent(question, rules=None):
    rules = rules or load_rules()
    ph = rules["phrases"]
    q = " " + question.lower().replace("%", " %") + " "
    it = Intent()
    it.germination = "germination" in q or "viab" in q or "retest" in q
    it.latest = _has(q, ph["latest"]) and it.germination
    it.no_retest = _has(q, ph["no_retest"])
    it.stock = _has(q, ph["stock"]) and not _has(q, ph["out_of_stock"])
    it.out_of_stock = _has(q, ph["out_of_stock"])
    it.storage_violation = _has(q, ph["storage_violation"]) or bool(
        re.search(r"(above|over|exceed\w*)\s+\d+(\.\d+)?\s*(c\b|°c|deg)|humidity\s+(above|over)|(above|over)\s+\d+(\.\d+)?\s*%\s*humidity", q))
    it.count = _has(q, ph["count"])
    it.group_each = _has(q, ph["group_each"])

    # germination threshold, e.g. "below 75%", "at least 75%", "75% or more"
    m = None
    for cand in re.finditer(r"(below|less than|under|lower than|at least|minimum of|above|more than|greater than|over)\s+(\d+(?:\.\d+)?)\s*%", q):
        around = q[max(0, cand.start() - 12):cand.end() + 12]
        if "humidity" not in around and "percentage point" not in q[cand.end():cand.end() + 20]:
            m = cand
            break
    m2 = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(or more|or above|or higher)", q)
    if it.germination and (m or m2):
        if m:
            word, val = m.group(1), float(m.group(2))
            it.threshold = val
            it.threshold_op = ("<" if word in ("below", "less than", "under", "lower than") else
                               ">=" if word in ("at least", "minimum of") else ">")
        else:
            it.threshold, it.threshold_op = float(m2.group(1)), ">="
    if "viable" in q and it.threshold is None:
        it.threshold, it.threshold_op = float(rules["defaults"]["germination_threshold"]), ">="
    if "viable" in q:
        it.latest = True  # viability is a property of the most recent test

    # storage limits, e.g. "above 15 C or above 50% humidity"
    t = re.search(r"(?:above|over|exceed\w*)\s+(\d+(?:\.\d+)?)\s*(?:c\b|°c|deg)", q)
    h = re.search(r"(?:above|over|exceed\w*)\s+(\d+(?:\.\d+)?)\s*%\s*humidity", q)
    if t:
        it.temp_limit = float(t.group(1))
    if h:
        it.hum_limit = float(h.group(1))
    if it.storage_violation and it.temp_limit is None:
        it.temp_limit = float(rules["defaults"]["max_storage_temperature_c"])
        it.hum_limit = it.hum_limit or float(rules["defaults"]["max_storage_humidity_pct"])

    # dates
    it.years = [int(y) for y in re.findall(r"\b(20\d\d|19\d\d)\b", q)]
    mf = re.search(r"(?:in|since|from)\s+(20\d\d)\s+or\s+later|since\s+(20\d\d)|(?:in|from)\s+(20\d\d)\s+onwards", q)
    if mf:
        it.year_from = int(next(g for g in mf.groups() if g))
    it.in_years = [int(y) for y in re.findall(r"\b(?:in|during)\s+(20\d\d)\b(?!\s+or\s+later)(?!\s+onwards)", q)]
    mb = re.search(r"before\s+(20\d\d|19\d\d)", q)
    if mb:
        it.year_before = int(mb.group(1))

    for lvl in ("High", "Medium", "Low"):
        if re.search(rf"\b{lvl.lower()}(ly)?\s+drought|drought[- ]tolerance\s+(level\s+)?'?{lvl.lower()}", q):
            it.drought = lvl
    if "highly drought" in q:
        it.drought = "High"

    # answer entity: what one output row is about
    # the "which X" head of the question decides first; secondary mentions ("at least one lot with") do not
    head = re.search(r"\b(which|list|show)\b([\w\s-]{0,40}?)\b(lots?|varieties|variety|storage location|destinations?|crop types?)\b", q)
    word = head.group(3) if head else ""
    if word.startswith("lot"):
        it.entity = "lot"
    elif word.startswith("variet") or "local name" in q:
        it.entity = "variety"
    elif word == "storage location" or re.search(r"\b(each|per) storage location", q):
        it.entity = "location"
    elif word.startswith("destination"):
        it.entity = "destination"
    elif re.search(r"\blots? (whose|that|which|stored|have|with)", q):
        it.entity = "lot"
    return it
