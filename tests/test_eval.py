"""Offline tests for the evaluation logic (no LLM needed).  Run:  python -m tests.test_eval   (or pytest)"""
from seedsql.db import SeedBankDB, error_category, extract_sql, results_match
from seedsql.prompts import BENCH

db = SeedBankDB()
gold = {q["id"]: db.run(q["gold_sql"]) for q in BENCH["questions"]}


def test_gold_queries_execute_and_self_match():
    for qid, r in gold.items():
        assert r["ok"] and results_match(r, r), qid


def test_equivalent_queries_match():
    assert results_match(gold["T1-01"], db.run(
        "SELECT local_name, crop_name, variety_id FROM SeedVariety WHERE drought_tolerance='High' ORDER BY local_name"))
    assert results_match(gold["T2-02"], db.run(
        "SELECT CAST(strftime('%Y',test_date) AS INTEGER) y, ROUND(AVG(germination_rate),2) FROM GerminationTest GROUP BY 1"))
    assert results_match(gold["T3-01"], db.run(
        "WITH l AS (SELECT lot_id, MAX(test_date) d FROM GerminationTest GROUP BY lot_id) "
        "SELECT g.lot_id, g.germination_rate FROM GerminationTest g JOIN l ON l.lot_id=g.lot_id AND l.d=g.test_date "
        "WHERE g.germination_rate < 75"))


def test_wrong_queries_do_not_match():
    assert not results_match(gold["T3-01"], db.run(
        "SELECT DISTINCT lot_id, germination_rate FROM GerminationTest WHERE germination_rate < 75"))
    assert not results_match(gold["T1-01"], db.run("SELECT local_name FROM SeedVariety WHERE drought_tolerance='High'"))
    assert not results_match(gold["T2-03"], db.run(
        "SELECT lot_id, COUNT(*) c FROM StorageLog WHERE temperature>15 AND humidity>50 GROUP BY lot_id ORDER BY c DESC LIMIT 5"))


def test_safety_and_errors():
    assert not db.run("DELETE FROM SeedLot")["ok"]
    assert not db.run("SELECT 1; DROP TABLE SeedLot")["ok"]
    assert error_category(db.run("SELECT foo FROM SeedLot")) == "Unknown column"
    assert error_category(db.run("SELECT FROM SeedLot")) == "Syntax error"
    assert extract_sql("text\n```sql\nSELECT 1;\n```") == "SELECT 1;"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("passed", name)
    print("ALL TESTS PASSED")
