"""Controlled database-state changes for OFFLINE evaluation (temporal robustness).

A query can match the gold answer on one database state by coincidence. Temporal robustness accuracy
(TRA) re-runs both the predicted and the gold query on several changed states (new germination tests,
stock exhausted or restocked, new distributions, new storage readings) and counts a question as robustly
correct only if the predicted result matches gold on the original AND on every changed state.

These random changes are independent of the validator's metamorphic tests (which are intent-driven and
use no gold); here the gold query is the oracle, so this is evaluation only, never used during inference.
"""
import random
import re

from .db import results_match

REF_DATE = "2026-11-01"


def _mutate(con, rng):
    lots = [r[0] for r in con.execute("SELECT lot_id FROM SeedLot")]
    rng.shuffle(lots)
    # 1. new germination tests (retests) on distinct lots, dated after every existing test, some crossing 75%
    for i, lot in enumerate(lots[:14]):
        con.execute("INSERT INTO GerminationTest (lot_id, test_date, germination_rate) VALUES (?, ?, ?)",
                    (lot, f"2026-11-{2 + i:02d}", round(rng.choice([rng.uniform(40, 74), rng.uniform(76, 98)]), 1)))
    # 2. stock exhausted / restocked
    for lot in lots[14:20]:
        con.execute("UPDATE SeedLot SET quantity = 0 WHERE lot_id = ?", (lot,))
    for lot in lots[20:23]:
        con.execute("UPDATE SeedLot SET quantity = quantity + ? WHERE lot_id = ?", (rng.randint(300, 2500), lot))
    # 3. new distributions
    dests = [r[0] for r in con.execute("SELECT DISTINCT destination FROM Distribution")]
    for lot in lots[23:26]:
        con.execute("INSERT INTO Distribution (lot_id, destination, quantity, date) VALUES (?, ?, ?, ?)",
                    (lot, rng.choice(dests), rng.choice([200, 500, 1000]), "2026-10-20"))
    # 4. new storage readings, some out of range
    for lot in lots[26:32]:
        con.execute("INSERT INTO StorageLog (lot_id, recorded_date, temperature, humidity) VALUES (?, ?, ?, ?)",
                    (lot, "2026-10-28", round(rng.uniform(5, 26), 1), round(rng.uniform(25, 70), 1)))
    # 5. next year's records arrive (the database keeps growing): a query without an upper date bound changes
    for lot in lots[32:36]:
        con.execute("INSERT INTO GerminationTest (lot_id, test_date, germination_rate) VALUES (?, ?, ?)",
                    (lot, "2027-02-10", round(rng.uniform(40, 98), 1)))
        con.execute("INSERT INTO StorageLog (lot_id, recorded_date, temperature, humidity) VALUES (?, ?, ?, ?)",
                    (lot, "2027-02-10", round(rng.uniform(5, 26), 1), round(rng.uniform(25, 70), 1)))
        con.execute("INSERT INTO Distribution (lot_id, destination, quantity, date) VALUES (?, ?, ?, ?)",
                    (lot, rng.choice(dests), 250, "2027-02-10"))


def _tie_at_limit(db, sql):
    m = re.search(r"ORDER BY (.+?) DESC LIMIT (\d+)", sql, re.I)
    if not m:
        return False
    k = int(m.group(2))
    full = db.run(re.split(r"\bLIMIT\b", sql, flags=re.I)[0])
    return full["ok"] and len(full["values"]) > k and full["values"][k - 1][-1] == full["values"][k][-1]


def robust_match(db, gold_sql, pred_sql, n_states=5, seed=0):
    """Returns (matches_on_original, matches_on_all_states, states_checked)."""
    gold, pred = db.run(gold_sql), db.run(pred_sql)
    base = results_match(gold, pred)
    if not base:
        return False, False, 0
    checked, attempt = 0, 0
    while checked < n_states and attempt < n_states * 5:
        attempt += 1
        mem, w = db.clone()
        _mutate(mem, random.Random(seed * 1000 + attempt))
        mem.commit()
        w.freeze()
        if _tie_at_limit(w, gold_sql):
            mem.close()
            continue  # an ambiguous top-k answer on this state: draw another state
        g, p = w.run(gold_sql), w.run(pred_sql)
        mem.close()
        checked += 1
        if not results_match(g, p):
            return True, False, checked
    return True, True, checked
