#!/usr/bin/env python3
"""Merge English translations into entries. Usage: python3 scripts/set_en.py translations.json
translations.json = {"<entry id>": {...en fields...}, ...}"""
import json, sys
from pathlib import Path
D = Path(__file__).resolve().parent.parent / "content" / "entries"
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for eid, en in data.items():
    f = D / f"{eid}.json"
    e = json.loads(f.read_text(encoding="utf-8"))
    e["en"] = en
    f.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    print("updated", eid)
