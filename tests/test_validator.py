"""Offline tests for the intent extractor, validator, mutation operators and robustness metric (no LLM).
Run:  python -m tests.test_validator   (or pytest)"""
import json

from seedsql.db import SeedBankDB, results_match
from seedsql.intent import extract_intent
from seedsql.mutants import mutants
from seedsql.perturb import robust_match
from seedsql.prompts import BENCH
from seedsql.validator import validate

db = SeedBankDB()
Q = {q["id"]: q for q in BENCH["questions"]}


def test_benchmark_size_and_categories():
    assert len(BENCH["questions"]) >= 60
    assert {q["category"] for q in BENCH["questions"]} == {"retrieval", "aggregation", "join", "temporal", "domain"}


def test_intent_extraction():
    it = extract_intent(Q["T3-01"]["question"])
    assert it.latest and it.threshold == 75 and it.threshold_op == "<" and it.entity == "lot"
    it = extract_intent(Q["T3-02"]["question"])
    assert it.stock and it.latest and it.threshold_op == ">=" and it.entity == "variety"
    assert extract_intent(Q["T2-03"]["question"]).storage_violation
    assert extract_intent(Q["T3-04"]["question"]).no_retest
    assert extract_intent(Q["DOM-12"]["question"]).threshold is None   # 50% belongs to humidity


def test_no_false_alarms_on_gold():
    bad = [q["id"] for q in BENCH["questions"] if not validate(q["question"], q["gold_sql"], db).ok]
    assert not bad, bad


def test_no_false_alarms_on_correct_rewrites():
    rew = json.load(open("data/equivalent_rewrites.json", encoding="utf-8"))["rewrites"]
    for qid, sqls in rew.items():
        for sql in sqls:
            assert results_match(db.run(Q[qid]["gold_sql"]), db.run(sql)), (qid, sql)
            assert validate(Q[qid]["question"], sql, db).ok, (qid, sql)


def test_detects_wrong_but_executing_mutants():
    missed, total = [], 0
    for q in BENCH["questions"]:
        gold = db.run(q["gold_sql"])
        for op, _, sql in mutants(q["gold_sql"]):
            res = db.run(sql)
            if res["ok"] and not results_match(gold, res):
                total += 1
                if validate(q["question"], sql, db, res=res).ok:
                    missed.append((q["id"], op))
    assert total >= 100
    assert len(missed) <= total * 0.05, missed


def test_metamorphic_latest_record():
    wrong = "SELECT DISTINCT lot_id, germination_rate FROM GerminationTest WHERE germination_rate < 75"
    rep = validate(Q["T3-01"]["question"], wrong, db)
    assert any(f.source == "metamorphic" and f.category == "temporal" for f in rep.findings)


def test_robustness_metric():
    for q in BENCH["questions"]:
        assert robust_match(db, q["gold_sql"], q["gold_sql"], n_states=2, seed=1) == (True, True, 2), q["id"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("passed", name)
    print("ALL VALIDATOR TESTS PASSED")
