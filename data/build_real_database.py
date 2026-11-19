"""
Builds the seed-bank database from REAL gene-bank accession records downloaded from Genesys
(https://www.genesys-pgr.org), e.g. the ICRISAT genebank (Patancheru, India).

    python data/build_real_database.py  path\\to\\genesys_download.csv   [--per-crop 8] [--seed 2026]

What is real and what is simulated (state this in the report):
  REAL       SeedVariety rows: accession number, genus, species, crop, accession name, origin country,
             acquisition date, biological status (landrace / cultivar / wild), holding genebank.
  ASSIGNED   crop_type and drought_tolerance: a crop-level rule (e.g. all pearl millet = 'High'),
             not measured per accession.
  SIMULATED  SeedLot, GerminationTest, StorageLog, Distribution: genebanks don't publish per-lot
             monitoring records, so these are generated (fixed seed) with the same model as the
             synthetic database: viability declines with years in storage, faster in poor storage.

Writes data/seedbank.db, data/seedbank.sql, and updates schema_text + dataset info in
data/benchmark.json. The previous database is backed up as data/seedbank_synthetic_backup.*
"""
import argparse
import csv
import io
import json
import os
import random
import re
import shutil
import sqlite3
import sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
REFERENCE_DATE = date(2026, 11, 1)

# genus (or genus+species) -> (crop label, crop_type, drought_tolerance)   [crop-level rule]
CROPS = [
    ("Eleusine coracana", "Finger millet", "Millet", "High"),
    ("Setaria italica", "Foxtail millet", "Millet", "High"),
    ("Panicum sumatrense", "Little millet", "Millet", "High"),
    ("Panicum miliaceum", "Proso millet", "Millet", "High"),
    ("Paspalum scrobiculatum", "Kodo millet", "Millet", "High"),
    ("Echinochloa", "Barnyard millet", "Millet", "High"),
    ("Pennisetum glaucum", "Pearl millet", "Millet", "High"),
    ("Cenchrus americanus", "Pearl millet", "Millet", "High"),
    ("Sorghum bicolor", "Sorghum", "Cereal", "High"),
    ("Oryza sativa", "Rice", "Cereal", "Low"),
    ("Cajanus cajan", "Pigeon pea", "Pulse", "Medium"),
    ("Cicer arietinum", "Chickpea", "Pulse", "Medium"),
    ("Vigna unguiculata", "Cowpea", "Pulse", "High"),
    ("Vigna radiata", "Green gram", "Pulse", "Medium"),
    ("Macrotyloma uniflorum", "Horse gram", "Pulse", "High"),
    ("Arachis hypogaea", "Groundnut", "Oilseed", "Medium"),
    ("Sesamum indicum", "Sesame", "Oilseed", "High"),
    ("Guizotia abyssinica", "Niger", "Oilseed", "High"),
    ("Solanum melongena", "Brinjal", "Vegetable", "Low"),
    ("Abelmoschus esculentus", "Okra", "Vegetable", "Medium"),
]
SAMPSTAT = {"1": "Wild", "2": "Weedy", "3": "Landrace", "4": "Breeding material", "5": "Improved cultivar",
            "9": "Other"}
LOCATIONS = {  # name: (temp mean, sd, humidity mean, sd, quality factor)   -- simulated
    "Cold Room A": (8.0, 2.0, 35.0, 5.0, 0.4), "Cold Room B": (10.0, 2.5, 38.0, 6.0, 0.6),
    "Clay Pot Store": (16.5, 3.5, 48.0, 8.0, 1.6), "Ambient Shelf": (20.0, 4.0, 54.0, 9.0, 2.4),
    "Village Hub - Mandya": (17.0, 3.5, 47.0, 8.0, 1.3)}
DESTINATIONS = ["Mandya Farmers Collective", "Tumakuru Millet Network", "Chitradurga Women SHG",
                "Kolar Organic Growers", "Hassan Seed Savers", "Mysuru School Garden",
                "Raichur Dryland Group", "Bengaluru Rural FPO"]

SCHEMA = """
CREATE TABLE SeedVariety (
    variety_id        INTEGER PRIMARY KEY,
    crop_name         TEXT NOT NULL,
    local_name        TEXT NOT NULL,      -- accession name, or accession number if unnamed
    crop_type         TEXT NOT NULL,
    drought_tolerance TEXT NOT NULL,
    accession_number  TEXT NOT NULL,      -- real genebank accession number (e.g. IS 1234)
    genebank          TEXT,               -- holding institute code (FAO WIEWS), e.g. IND002
    scientific_name   TEXT,
    origin_country    TEXT,               -- ISO 3166 alpha-3, e.g. IND
    biological_status TEXT,               -- Landrace / Improved cultivar / Wild / ...
    acquisition_date  TEXT                -- date the genebank acquired the accession
);
CREATE TABLE SeedLot (
    lot_id INTEGER PRIMARY KEY, variety_id INTEGER NOT NULL REFERENCES SeedVariety(variety_id),
    storage_location TEXT NOT NULL, quantity INTEGER NOT NULL, collection_date TEXT NOT NULL);
CREATE TABLE GerminationTest (
    test_id INTEGER PRIMARY KEY, lot_id INTEGER NOT NULL REFERENCES SeedLot(lot_id),
    test_date TEXT NOT NULL, germination_rate REAL NOT NULL);
CREATE TABLE StorageLog (
    log_id INTEGER PRIMARY KEY, lot_id INTEGER NOT NULL REFERENCES SeedLot(lot_id),
    recorded_date TEXT NOT NULL, temperature REAL NOT NULL, humidity REAL NOT NULL);
CREATE TABLE Distribution (
    distribution_id INTEGER PRIMARY KEY, lot_id INTEGER NOT NULL REFERENCES SeedLot(lot_id),
    destination TEXT NOT NULL, quantity INTEGER NOT NULL, date TEXT NOT NULL);
""".strip()

ALIASES = {  # MCPD names and common Genesys / Darwin Core alternatives
    "instcode": ["instcode", "institutecode", "institutioncode", "instituteCode"],
    "accenumb": ["accenumb", "accessionnumber", "catalognumber", "accessionNumber", "acceNumb"],
    "genus": ["genus"],
    "species": ["species", "specificepithet"],
    "cropname": ["cropname", "cropName", "crop"],
    "accename": ["accename", "accessionname", "acceName"],
    "acqdate": ["acqdate", "acquisitiondate", "acqDate"],
    "origcty": ["origcty", "origincountry", "countryoforigin", "origCty", "country"],
    "sampstat": ["sampstat", "biologicalstatus", "sampStat"],
    "sciname": ["scientificname", "taxonomy", "fullname"],
}


def read_rows(path):
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:5000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
    if not rows:
        sys.exit("The file has no data rows.")
    norm = {re.sub(r"[^a-z]", "", k.lower()): k for k in rows[0].keys() if k}
    cols = {}
    for key, names in ALIASES.items():
        for n in names:
            k = re.sub(r"[^a-z]", "", n.lower())
            if k in norm:
                cols[key] = norm[k]
                break
    missing = [k for k in ("accenumb",) if k not in cols]
    if missing or ("genus" not in cols and "sciname" not in cols):
        sys.exit(f"Could not find accession number / genus columns. Columns found: {list(rows[0].keys())[:30]}")
    return rows, cols


def classify(genus, species):
    name = f"{genus} {species}".strip().lower()
    for key, crop, ctype, drought in CROPS:
        k = key.lower()
        if name.startswith(k) or (" " not in k and genus.lower() == k):
            return crop, ctype, drought
    return None


def parse_acq(v):
    v = (v or "").strip().replace("-", "")
    m = re.match(r"^(\d{4})(\d{2})?(\d{2})?", v)
    if not m or not (1900 < int(m.group(1)) <= REFERENCE_DATE.year):
        return None
    y = int(m.group(1)); mo = int(m.group(2) or 0) or 1; d = int(m.group(3) or 0) or 1
    try:
        return date(y, min(mo, 12), min(d, 28)).isoformat()
    except ValueError:
        return f"{y}-01-01"


def build(rows, cols, per_crop, seed):
    rng = random.Random(seed)
    g = lambda r, k: (r.get(cols[k]) or "").strip() if k in cols else ""
    by_crop = {}
    for r in rows:
        genus, species = g(r, "genus"), g(r, "species")
        if not genus and g(r, "sciname"):
            parts = g(r, "sciname").split()
            genus, species = parts[0], (parts[1] if len(parts) > 1 else "")
        c = classify(genus, species)
        if not c or not g(r, "accenumb"):
            continue
        by_crop.setdefault(c, []).append((r, genus, species))
    if not by_crop:
        sys.exit("No accessions of the supported crops were found in the file (millets, sorghum, pulses, groundnut...).")
    varieties = []
    for (crop, ctype, drought), items in sorted(by_crop.items()):
        named = [x for x in items if g(x[0], "accename")]
        pool = named if len(named) >= per_crop else items
        for r, genus, species in rng.sample(pool, min(per_crop, len(pool))):
            st = g(r, "sampstat")
            varieties.append(dict(
                crop_name=crop, local_name=g(r, "accename") or g(r, "accenumb"), crop_type=ctype,
                drought_tolerance=drought, accession_number=g(r, "accenumb"), genebank=g(r, "instcode") or None,
                scientific_name=f"{genus} {species}".strip(), origin_country=g(r, "origcty") or None,
                biological_status=SAMPSTAT.get(st[:1], None) if st else None,
                acquisition_date=parse_acq(g(r, "acqdate"))))
    # make local names unique (questions return local names)
    seen = {}
    for v in varieties:
        n = v["local_name"]
        if n in seen:
            v["local_name"] = f"{n} ({v['accession_number']})"
        seen[n] = 1

    lots, tests, logs, dists = [], [], [], []
    lid = tid = gid = did = 0
    locs = list(LOCATIONS)
    for vid, v in enumerate(varieties, start=1):
        for _ in range(rng.choice([1, 2, 2, 3])):
            lid += 1
            loc = rng.choices(locs, weights=[3, 3, 2, 2, 2])[0]
            regen = date(rng.randint(2012, 2025), rng.randint(1, 12), rng.randint(1, 28))  # seed regeneration
            qty = rng.choice([0] + [rng.randint(150, 4000) for _ in range(8)])
            lots.append((lid, vid, loc, qty, regen.isoformat()))
            tm, ts, hm, hs, q = LOCATIONS[loc]
            base = rng.uniform(88, 97)
            span = (REFERENCE_DATE - regen).days
            for td in sorted(regen + timedelta(days=rng.randint(30, max(31, span - 20)))
                             for _ in range(rng.choice([1, 2, 2, 3, 3, 4]))):
                yrs = (td - regen).days / 365.0
                rate = round(max(18.0, min(99.0, base - yrs * q * rng.uniform(1.2, 3.2) - rng.uniform(0, 4))), 1)
                tid += 1
                tests.append((tid, lid, td.isoformat(), rate))
            bias = rng.uniform(-2.5, 2.5)
            d = max(regen, date(2022, 6, 1) + timedelta(days=rng.randint(0, 1100)))
            while d <= REFERENCE_DATE:
                gid += 1
                logs.append((gid, lid, d.isoformat(), round(rng.gauss(tm + bias, ts), 1),
                             round(min(95, max(15, rng.gauss(hm + bias * 2, hs))), 1)))
                d = (d.replace(day=1) + timedelta(days=32)).replace(day=min(d.day, 28))
            for _ in range(rng.choice([0, 0, 1, 1, 2, 3])):
                did += 1
                dd = regen + timedelta(days=rng.randint(60, max(61, span - 1)))
                dists.append((did, lid, rng.choice(DESTINATIONS), rng.choice([100, 200, 250, 300, 500, 750, 1000]),
                              dd.isoformat()))
    vrows = [(i, v["crop_name"], v["local_name"], v["crop_type"], v["drought_tolerance"], v["accession_number"],
              v["genebank"], v["scientific_name"], v["origin_country"], v["biological_status"], v["acquisition_date"])
             for i, v in enumerate(varieties, start=1)]
    return [("SeedVariety", vrows), ("SeedLot", lots), ("GerminationTest", tests), ("StorageLog", logs),
            ("Distribution", dists)]


def lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def schema_text(con):
    vals = lambda sql: ",".join("'" + r[0] + "'" for r in con.execute(sql))
    return f"""SeedVariety(variety_id INTEGER PK, crop_name TEXT, local_name TEXT, crop_type TEXT, drought_tolerance TEXT, accession_number TEXT, genebank TEXT, scientific_name TEXT, origin_country TEXT, biological_status TEXT, acquisition_date TEXT)
  -- one row per real genebank accession; local_name = accession name (or accession number if unnamed)
  -- crop_type values: {vals("SELECT DISTINCT crop_type FROM SeedVariety ORDER BY 1")}
  -- drought_tolerance values: {vals("SELECT DISTINCT drought_tolerance FROM SeedVariety ORDER BY 1")}
  -- crop_name values: {vals("SELECT DISTINCT crop_name FROM SeedVariety ORDER BY 1")}
  -- origin_country is an ISO 3166 alpha-3 code (e.g. 'IND'); biological_status values: {vals("SELECT DISTINCT biological_status FROM SeedVariety WHERE biological_status IS NOT NULL ORDER BY 1")}
SeedLot(lot_id INTEGER PK, variety_id INTEGER FK->SeedVariety.variety_id, storage_location TEXT, quantity INTEGER, collection_date TEXT)
  -- storage_location values: {vals("SELECT DISTINCT storage_location FROM SeedLot ORDER BY 1")}
  -- quantity = grams currently in stock (0 means exhausted); collection_date = date this seed lot was harvested/regenerated
GerminationTest(test_id INTEGER PK, lot_id INTEGER FK->SeedLot.lot_id, test_date TEXT, germination_rate REAL)
  -- germination_rate is a percentage 0-100; a lot can have several tests over time
StorageLog(log_id INTEGER PK, lot_id INTEGER FK->SeedLot.lot_id, recorded_date TEXT, temperature REAL, humidity REAL)
  -- monthly readings; temperature in deg C, humidity in % relative humidity
Distribution(distribution_id INTEGER PK, lot_id INTEGER FK->SeedLot.lot_id, destination TEXT, quantity INTEGER, date TEXT)
  -- seed given out to farmer groups; quantity in grams
Notes: all dates are TEXT 'YYYY-MM-DD'. The database engine is SQLite. Today's date is 2026-11-01."""


def check_benchmark(con, bench):
    problems = []
    for q in bench["questions"]:
        try:
            rows = con.execute(q["gold_sql"]).fetchall()
        except sqlite3.Error as e:
            problems.append(f"{q['id']}: {e}")
            continue
        if not rows:
            problems.append(f"{q['id']}: gold query returns 0 rows")
        m = re.search(r"ORDER BY (.+?) DESC LIMIT (\d+)", q["gold_sql"])
        if m:  # tie at the LIMIT boundary would make the answer ambiguous
            n = int(m.group(2))
            full = con.execute(q["gold_sql"].rsplit("LIMIT", 1)[0]).fetchall()
            if len(full) > n and full[n - 1][-1] == full[n][-1]:
                problems.append(f"{q['id']}: tie at LIMIT {n}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_file")
    ap.add_argument("--per-crop", type=int, default=6, help="accessions sampled per crop")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    rows, cols = read_rows(a.csv_file)
    print(f"Read {len(rows)} accession rows. Columns used: {cols}")
    bench_path = os.path.join(HERE, "benchmark.json")
    bench = json.load(open(bench_path, encoding="utf-8"))

    for seed in range(a.seed, a.seed + 200):  # find a sample where every gold query is well-defined
        tables = build(rows, cols, a.per_crop, seed)
        lines = ["-- Community seed-bank database: REAL Genesys accession records + simulated lot monitoring.", SCHEMA]
        for name, rs in tables:
            lines += [f"INSERT INTO {name} VALUES ({', '.join(lit(x) for x in r)});" for r in rs]
        script = "\n".join(lines) + "\n"
        con = sqlite3.connect(":memory:")
        con.executescript(script)
        problems = check_benchmark(con, bench)
        if not problems:
            break
    else:
        print("Warning: some benchmark questions are ill-defined on this data:", problems)
    for ext in ("db", "sql"):
        src = os.path.join(HERE, f"seedbank.{ext}")
        bak = os.path.join(HERE, f"seedbank_synthetic_backup.{ext}")
        if os.path.exists(src) and not os.path.exists(bak):
            shutil.copy(src, bak)
    open(os.path.join(HERE, "seedbank.sql"), "w", encoding="utf-8").write(script)
    dbp = os.path.join(HERE, "seedbank.db")
    if os.path.exists(dbp):
        os.remove(dbp)
    disk = sqlite3.connect(dbp)
    disk.executescript(script)
    disk.commit()
    banks = sorted({r[0] for r in disk.execute("SELECT DISTINCT genebank FROM SeedVariety WHERE genebank IS NOT NULL")})
    bench["schema_text"] = schema_text(disk)
    bench["dataset"] = {
        "kind": "real-accessions",
        "note": (f"SeedVariety holds {disk.execute('SELECT COUNT(*) FROM SeedVariety').fetchone()[0]} REAL genebank "
                 f"accessions from Genesys (genebank {', '.join(banks) or 'see file'}); crop_type and drought "
                 "tolerance follow a crop-level rule; seed lots, germination tests, storage logs and distributions "
                 "are simulated (fixed seed) because genebanks do not publish per-lot monitoring records."),
        "source_file": os.path.basename(a.csv_file), "sample_seed": seed}
    json.dump(bench, open(bench_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    for name, _ in tables:
        print(f"{name:16s} {disk.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]:5d} rows")
    print("Crops:", ", ".join(f"{c} ({n})" for c, n in disk.execute(
        "SELECT crop_name, COUNT(*) FROM SeedVariety GROUP BY 1 ORDER BY 2 DESC")))
    print(f"Sample seed {seed}; benchmark check: {'all 18 gold queries well-defined' if not problems else problems}")
    print("Done. Now run:  python web/build.py   then   python -m tests.test_eval")


if __name__ == "__main__":
    main()
