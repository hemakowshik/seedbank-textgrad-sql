"""
Builds the synthetic Community Seed-Bank database used by the project.

All records are SYNTHETIC (generated with a fixed random seed) and do not
describe any real seed bank. Variety names are common Karnataka crop / landrace
names used only to make the demo realistic.

Outputs (next to this script):
    seedbank.db   - SQLite database
    seedbank.sql  - same database as a plain SQL script (schema + INSERTs)

Run:  python data/build_database.py
"""
import os
import random
import sqlite3
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "seedbank.db")
SQL_PATH = os.path.join(HERE, "seedbank.sql")

REFERENCE_DATE = date(2026, 11, 1)   # "today" for the dataset
GERM_THRESHOLD = 75                  # % - retest threshold (demo assumption)
MAX_TEMP = 15.0                      # deg C - recommended storage max (demo assumption)
MAX_HUMIDITY = 50.0                  # % RH - recommended storage max (demo assumption)

SCHEMA = """
CREATE TABLE SeedVariety (
    variety_id        INTEGER PRIMARY KEY,
    crop_name         TEXT NOT NULL,      -- e.g. 'Finger millet'
    local_name        TEXT NOT NULL,      -- local landrace / variety name
    crop_type         TEXT NOT NULL,      -- 'Millet','Cereal','Pulse','Vegetable','Oilseed'
    drought_tolerance TEXT NOT NULL       -- 'High','Medium','Low'
);
CREATE TABLE SeedLot (
    lot_id           INTEGER PRIMARY KEY,
    variety_id       INTEGER NOT NULL REFERENCES SeedVariety(variety_id),
    storage_location TEXT NOT NULL,
    quantity         INTEGER NOT NULL,    -- grams currently in stock (0 = exhausted)
    collection_date  TEXT NOT NULL        -- 'YYYY-MM-DD'
);
CREATE TABLE GerminationTest (
    test_id          INTEGER PRIMARY KEY,
    lot_id           INTEGER NOT NULL REFERENCES SeedLot(lot_id),
    test_date        TEXT NOT NULL,       -- 'YYYY-MM-DD'
    germination_rate REAL NOT NULL        -- percent, 0-100
);
CREATE TABLE StorageLog (
    log_id        INTEGER PRIMARY KEY,
    lot_id        INTEGER NOT NULL REFERENCES SeedLot(lot_id),
    recorded_date TEXT NOT NULL,          -- 'YYYY-MM-DD'
    temperature   REAL NOT NULL,          -- deg C
    humidity      REAL NOT NULL           -- % relative humidity
);
CREATE TABLE Distribution (
    distribution_id INTEGER PRIMARY KEY,
    lot_id          INTEGER NOT NULL REFERENCES SeedLot(lot_id),
    destination     TEXT NOT NULL,        -- receiving farmer group / village
    quantity        INTEGER NOT NULL,     -- grams distributed
    date            TEXT NOT NULL         -- 'YYYY-MM-DD'
);
""".strip()

VARIETIES = [
    # crop_name, local_name, crop_type, drought_tolerance
    ("Finger millet", "Hasiru Ragi", "Millet", "High"),
    ("Finger millet", "Kari Ragi", "Millet", "High"),
    ("Finger millet", "Majjige Ragi", "Millet", "Medium"),
    ("Foxtail millet", "Kempu Navane", "Millet", "High"),
    ("Little millet", "Saame", "Millet", "High"),
    ("Kodo millet", "Haraka", "Millet", "High"),
    ("Pearl millet", "Sajje", "Millet", "High"),
    ("Sorghum", "Maldandi Jola", "Cereal", "High"),
    ("Sorghum", "Bili Jola", "Cereal", "Medium"),
    ("Rice", "Rajamudi", "Cereal", "Low"),
    ("Rice", "Gandhasale", "Cereal", "Low"),
    ("Rice", "Navara", "Cereal", "Medium"),
    ("Rice", "Mysore Mallige", "Cereal", "Low"),
    ("Rice", "Doddabyra", "Cereal", "Medium"),
    ("Horse gram", "Huruli", "Pulse", "High"),
    ("Field bean", "Avare", "Pulse", "Medium"),
    ("Cowpea", "Alasande", "Pulse", "High"),
    ("Pigeon pea", "Gulbarga Togari", "Pulse", "Medium"),
    ("Green gram", "Hesaru", "Pulse", "Medium"),
    ("Brinjal", "Mattu Gulla", "Vegetable", "Low"),
    ("Tomato", "Nati Tomato", "Vegetable", "Low"),
    ("Okra", "Nati Bende", "Vegetable", "Medium"),
    ("Ridge gourd", "Heerekai", "Vegetable", "Low"),
    ("Chilli", "Byadgi Menasu", "Vegetable", "Medium"),
    ("Groundnut", "Nati Kadale", "Oilseed", "Medium"),
    ("Niger", "Huchellu", "Oilseed", "High"),
    ("Sesame", "Ellu", "Oilseed", "High"),
    ("Safflower", "Kusube", "Oilseed", "High"),
]

LOCATIONS = {
    # name: (temp_mean, temp_sd, hum_mean, hum_sd)  -> storage quality
    "Cold Room A": (8.0, 2.0, 35.0, 5.0),
    "Cold Room B": (10.0, 2.5, 38.0, 6.0),
    "Clay Pot Store": (16.5, 3.5, 48.0, 8.0),
    "Ambient Shelf": (20.0, 4.0, 54.0, 9.0),
    "Village Hub - Mandya": (17.0, 3.5, 47.0, 8.0),
}
LOC_QUALITY = {"Cold Room A": 0.4, "Cold Room B": 0.6, "Clay Pot Store": 1.6,
               "Ambient Shelf": 2.4, "Village Hub - Mandya": 1.3}

DESTINATIONS = [
    "Mandya Farmers Collective", "Tumakuru Millet Network", "Chitradurga Women SHG",
    "Kolar Organic Growers", "Hassan Seed Savers", "Mysuru School Garden",
    "Raichur Dryland Group", "Bengaluru Rural FPO",
]


def d2s(d):
    return d.isoformat()


def build(rng):
    lots, tests, logs, dists = [], [], [], []
    lot_id = test_id = log_id = dist_id = 0
    loc_names = list(LOCATIONS)
    for vid, var in enumerate(VARIETIES, start=1):
        n_lots = rng.choice([2, 3, 3, 4])
        for _ in range(n_lots):
            lot_id += 1
            loc = rng.choices(loc_names, weights=[3, 3, 2, 2, 2])[0]
            coll = date(rng.randint(2016, 2025), rng.randint(1, 12), rng.randint(1, 28))
            qty = rng.choice([0] + [rng.randint(150, 4000) for _ in range(8)])
            lots.append((lot_id, vid, loc, qty, d2s(coll)))

            # germination tests: decline with age and poor storage
            base = rng.uniform(88, 97)
            n_tests = rng.choice([1, 2, 2, 3, 3, 4])
            span_days = (REFERENCE_DATE - coll).days
            tdates = sorted(coll + timedelta(days=rng.randint(30, max(31, span_days - 20)))
                            for _ in range(n_tests))
            for td in tdates:
                years = (td - coll).days / 365.0
                rate = base - years * LOC_QUALITY[loc] * rng.uniform(1.2, 3.2) - rng.uniform(0, 4)
                rate = round(max(18.0, min(99.0, rate)), 1)
                test_id += 1
                tests.append((test_id, lot_id, d2s(td), rate))

            # storage logs: monthly readings; logging started at different times per lot
            tm, ts, hm, hs = LOCATIONS[loc]
            lot_bias = rng.uniform(-2.5, 2.5)
            start = max(coll, date(2022, 6, 1) + timedelta(days=rng.randint(0, 1100)))
            d = start
            while d <= REFERENCE_DATE:
                log_id += 1
                logs.append((log_id, lot_id, d2s(d),
                             round(rng.gauss(tm + lot_bias, ts), 1),
                             round(min(95, max(15, rng.gauss(hm + lot_bias * 2, hs))), 1)))
                d = (d.replace(day=1) + timedelta(days=32)).replace(day=min(d.day, 28))

            # distributions
            for _ in range(rng.choice([0, 0, 1, 1, 2, 3])):
                dist_id += 1
                dd = coll + timedelta(days=rng.randint(60, max(61, span_days - 1)))
                dists.append((dist_id, lot_id, rng.choice(DESTINATIONS),
                              rng.choice([100, 200, 250, 300, 500, 750, 1000]), d2s(dd)))
    return lots, tests, logs, dists


def sql_literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def main():
    rng = random.Random(2026)
    lots, tests, logs, dists = build(rng)
    varieties = [(i, *v) for i, v in enumerate(VARIETIES, start=1)]
    tables = [("SeedVariety", varieties), ("SeedLot", lots), ("GerminationTest", tests),
              ("StorageLog", logs), ("Distribution", dists)]

    lines = ["-- Community Seed-Bank synthetic database (seed=2026). Synthetic data only.",
             SCHEMA]
    for name, rows in tables:
        for r in rows:
            lines.append(f"INSERT INTO {name} VALUES ({', '.join(sql_literal(x) for x in r)});")
    script = "\n".join(lines) + "\n"
    with open(SQL_PATH, "w", encoding="utf-8") as f:
        f.write(script)

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.executescript(script)
    con.commit()
    for name, _ in tables:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"{name:16s} {n:5d} rows")
    con.close()
    print("Wrote", DB_PATH, "and", SQL_PATH)


if __name__ == "__main__":
    main()
