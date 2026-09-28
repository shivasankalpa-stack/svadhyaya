#!/usr/bin/env python3
"""Extract Sri Hari's mantra posts and Kusha N M's poems from a WhatsApp chat export.

Usage: python3 scripts/extract.py path/to/WhatsApp-Chat.txt [--since YYYY-MM-DD]

Writes one JSON file per entry to content/entries/. Existing files keep their
English translation ("en") and any manual edits to "kn"; only new entries are
created. Entries still needing translation are listed at the end.
"""
import json, re, sys, os, datetime, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "content" / "entries"
CFG = json.loads((ROOT / "scripts" / "rules.json").read_text(encoding="utf-8"))

HDR = re.compile(r'^(\d{1,2}/\d{1,2}/\d{2,4}), (\d{1,2}:\d{2})[\s ]?([AaPp][Mm]) - (.*)$')

def parse_chat(path):
    msgs = []
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        line = line.replace("‎", "")
        m = HDR.match(line)
        if m:
            d, t, ap, rest = m.groups()
            mo, dd, yy = d.split("/")
            yy = int(yy); yy = yy + 2000 if yy < 100 else yy
            hh, mi = map(int, t.split(":"))
            if ap.upper() == "PM" and hh != 12: hh += 12
            if ap.upper() == "AM" and hh == 12: hh = 0
            dt = datetime.datetime(yy, int(mo), int(dd), hh, mi)
            sender, text = (rest.split(": ", 1) if ": " in rest else (None, rest))
            msgs.append({"dt": dt, "sender": sender, "text": text})
        elif msgs:
            msgs[-1]["text"] += "\n" + line
    for i, m in enumerate(msgs):
        m["key"] = m["dt"].strftime("%Y%m%d%H%M") + f"-{abs(hash(m['text'][:40])) % 10000:04d}"
        m["text"] = re.sub(r"\s*<This message was edited>\s*$", "", m["text"]).strip()
    return msgs

def fingerprint(m):
    # stable id for a message across exports: timestamp + first 30 chars
    return m["dt"].strftime("%Y-%m-%dT%H:%M") + "|" + re.sub(r"\s+", "", m["text"])[:30]

MARK = re.compile(r"ಭಾವಾರ್ಥ|ಪ್ರತಿ\s*ಪದಾರ್ಥ")
POEM_END = re.compile(r"ಮೂಢ\s*ಮನುಜ\S*\s*[.!]*$")
CONT = re.compile(r"^\s*(Part\s*\d|ಮುಂದುವರ)|\(ಮುಂದುವರೆದ\)|ಮುಂದುವರಿದ ಭಾಗ")

def classify(m):
    s, t = m["sender"], m["text"]
    fp = fingerprint(m)
    if fp in CFG["exclude"]: return None
    if fp in CFG["include_note"]: return "note"
    for typ, fps in CFG.get("manual", {}).items():
        if fp in fps: return typ
    if fp in CFG["include_mantra"]: return "mantra"
    if s in CFG["poet_senders"]:
        lines = [l for l in t.split("\n") if l.strip()]
        body = t.split("\n\n")[0]
        if POEM_END.search(body.strip()) and len([l for l in body.split("\n") if l.strip()]) == 4:
            return "poem"
        return None
    if s in CFG["mantra_senders"]:
        if "<Media omitted>" in t or "This message was deleted" in t: return None
        if MARK.search(t) and not re.search(r"ನಾಳೆಯಿಂದ", t[:400]) :
            return "mantra"
        return None
    return None

# ---------- structure a mantra post ----------
SEC = re.compile(r"^\(?(ಸಂಹಿತಾ\s*ಪಾಠ|ಪ್ರತಿ\s*ಪದಾರ್ಥ|\(?ಮುಂದುವರೆದ\)?\s*ಭಾವಾರ್ಥ|ಭಾವಾರ್ಥ|ವಿಶೇಷ\s*ವಿಷಯ)\)?\s*:?\s*$")
META = re.compile(r"^(ಋಷಿ|ಋಷೀ|ಋಷಯ|ದೇವತಾ|ದೇವತೆ|ಛಂದ|ಛಂದಸ್ಸು|ಮಂಡಲ|ಅಷ್ಟಕ|ಅಧ್ಯಾಯ|ಅನುವಾಕ|ವರ್ಗ|ಸೂಕ್ತ\s*[-೦-೯0-9]|ಸೂಕ್ತ\s*ದಲ್ಲಿರುವ)")
KN_NUM = str.maketrans("೦೧೨೩೪೫೬೭೮೯", "0123456789")

def structure_mantra(t):
    lines = [l.rstrip() for l in t.split("\n")]
    title, series, number = None, None, None
    first = lines[0].strip() if lines else ""
    mt = re.match(r"^(.*?)(?:\s*[/,]?\s*)ಮಂತ್ರ\s*([೦-೯0-9]+)\s*$", first)
    if mt and len(first) < 70:
        title = first
        series = mt.group(1).strip(" ,/") or None
        number = int(mt.group(2).translate(KN_NUM))
        lines = lines[1:]
    sections = {"mantra": [], "pratipada": [], "bhavartha": [], "vishesha": [], "meta": []}
    cur = "mantra"
    for l in lines:
        s = l.strip()
        if not s: 
            if cur != "mantra": sections[cur].append("")
            continue
        h = SEC.match(s)
        if h:
            name = h.group(1)
            if "ಸಂಹಿತಾ" in name: cur = "mantra"
            elif "ಪದಾರ್ಥ" in name: cur = "pratipada"
            elif "ಭಾವಾರ್ಥ" in name: cur = "bhavartha"
            else: cur = "vishesha"
            continue
        if cur == "mantra" and META.match(s):
            sections["meta"].append(s); continue
        sections[cur].append(s)
    gloss = []
    for s in sections["pratipada"]:
        if not s: continue
        g = re.match(r"^(.+?)\s*(?::\s*-|:-|\s-\s?|-\s)\s*(.+)$", s)
        if g and len(g.group(1)) < 40: gloss.append([g.group(1).strip(), g.group(2).strip()])
        else:
            g2 = re.match(r"^(\S+?)\s*[.:]\s+(.+)$", s)
            g3 = re.match(r"^([^\s-]{1,25})-(.+)$", s)
            if g2 and len(g2.group(1)) < 30: gloss.append([g2.group(1), g2.group(2)])
            elif g3: gloss.append([g3.group(1), g3.group(2)])
            elif gloss and gloss[-1][0] and not s.startswith("("): gloss[-1][1] += " " + s
            else: gloss.append(["", s])
    clean = lambda arr: "\n".join(arr).strip()
    return {
        "title": title, "series": series, "number": number,
        "meta": sections["meta"],
        "mantra": clean(sections["mantra"]),
        "gloss": gloss,
        "bhavartha": clean(sections["bhavartha"]),
        "vishesha": clean(sections["vishesha"]),
    }

def structure_note(t):
    lines = t.strip().split("\n")
    title = lines[0].strip() if len(lines[0]) < 80 else None
    body = "\n".join(lines[1:]).strip() if title else t.strip()
    return {"title": title, "body": body}

def structure_poem(t):
    parts = t.strip().split("\n\n", 1)
    lines = [l.strip() for l in parts[0].split("\n") if l.strip()]
    return {"lines": lines, "footnote": parts[1].strip() if len(parts) > 1 else ""}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chat"); ap.add_argument("--since")
    a = ap.parse_args()
    msgs = parse_chat(a.chat)
    picked = []
    for m in msgs:
        if a.since and m["dt"].date().isoformat() < a.since: continue
        c = classify(m)
        if not c and fingerprint(m) not in CFG["merge_with_previous"]: continue
        # merge continuation messages from same author within 30 minutes
        prev = next((x for x in reversed(picked) if x["sender"] == m["sender"] and x["type"] != "poem"), None)
        if prev and (fingerprint(m) in CFG["merge_with_previous"] or (c and c != "poem" and \
           (m["dt"] - prev["dt"]).total_seconds() < 1800 and CONT.search(m["text"][:120]))):
            prev["text"] += "\n\n" + m["text"]; continue
        if not c: continue
        m["type"] = c; picked.append(m)
    OUT.mkdir(parents=True, exist_ok=True)
    existing = {}
    for f in OUT.glob("*.json"):
        e = json.loads(f.read_text(encoding="utf-8")); existing[e["source"]] = f
    created, pending = [], []
    counts = {}
    for m in picked:
        fp = fingerprint(m)
        if fp in existing:
            e = json.loads(existing[fp].read_text(encoding="utf-8"))
            if not e.get("en"): pending.append(existing[fp].name)
            continue
        day = m["dt"].date().isoformat()
        k = (day, m["type"]); counts[k] = counts.get(k, 0) + 1
        eid = f"{day}-{m['type']}" + (f"-{counts[k]}" if counts[k] > 1 else "")
        while (OUT / f"{eid}.json").exists():
            counts[k] += 1; eid = f"{day}-{m['type']}-{counts[k]}"
        author = CFG["authors"][m["sender"]]
        kn = {"mantra": structure_mantra, "note": structure_note, "poem": structure_poem}.get(m["type"], structure_note)(m["text"])
        entry = {"id": eid, "type": m["type"], "date": day, "time": m["dt"].strftime("%H:%M"),
                 "author": author, "source": fp, "kn": kn, "raw": m["text"], "en": None}
        (OUT / f"{eid}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding="utf-8")
        created.append(eid); pending.append(f"{eid}.json")
    print(f"messages: {len(msgs)}  picked: {len(picked)}  new: {len(created)}")
    print("needs translation:", len(pending))
    for p in sorted(pending)[-10:]: print("  ", p)

if __name__ == "__main__":
    main()
