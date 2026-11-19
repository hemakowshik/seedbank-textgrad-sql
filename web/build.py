"""Injects the database SQL and benchmark into the web app -> web/index.html"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
tpl = open(os.path.join(HERE, "app.template.html"), encoding="utf-8").read()
sql = open(os.path.join(ROOT, "data", "seedbank.sql"), encoding="utf-8").read()
bench = json.load(open(os.path.join(ROOT, "data", "benchmark.json"), encoding="utf-8"))
assert "</script" not in sql.lower()
bj = json.dumps(bench, ensure_ascii=False).replace("</", "<\\/")
out = tpl.replace("__SEED_SQL__", sql).replace("__BENCH_JSON__", bj)
open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(out)
print("wrote web/index.html", len(out)//1024, "KB")
