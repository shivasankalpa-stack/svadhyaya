#!/usr/bin/env python3
"""Build the Svādhyāya static site from content/ into public/.

    python3 build.py
Requires indic_transliteration (see requirements.txt) for romanization; builds without it too.
"""
import json, re, shutil, datetime, html
from pathlib import Path
from collections import OrderedDict

try:
    from indic_transliteration import sanscript as SC
except ImportError:
    SC = None

ROOT = Path(__file__).resolve().parent
CONTENT, OUT, STATIC = ROOT / "content", ROOT / "public", ROOT / "static"
SITE = json.loads((CONTENT / "site.json").read_text(encoding="utf-8"))
AUTH = SITE["authors"]
COLS = SITE["collections"]
COL_OF_TYPE = {t: c for c in COLS for t in c["types"]}

def esc(s): return html.escape((s or "").replace("�", ""), quote=True)
KN_DIGITS = str.maketrans("0123456789", "೦೧೨೩೪೫೬೭೮೯")
KN_WEEK = ["ಸೋಮವಾರ", "ಮಂಗಳವಾರ", "ಬುಧವಾರ", "ಗುರುವಾರ", "ಶುಕ್ರವಾರ", "ಶನಿವಾರ", "ಭಾನುವಾರ"]
KN_MONTH = ["ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್", "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"]
def D(s): return datetime.date.fromisoformat(s)
def en_date(d, weekday=True): return (d.strftime("%A, ") if weekday else "") + f"{d.day} {d.strftime('%B %Y')}"
def en_short(d): return f"{d.day} {d.strftime('%b %Y')}"
def kn_num(n): return str(n).translate(KN_DIGITS)
def kn_date(d, weekday=True): return (f"{KN_WEEK[d.weekday()]}, " if weekday else "") + f"{kn_num(d.day)} {KN_MONTH[d.month-1]} {kn_num(d.year)}"
def bi(kn, en, cls=""):
    """A bilingual inline pair; CSS shows one or both depending on the language mode."""
    return f'<span class="kn-only-inline{cls}" lang="kn">{kn}</span><span class="en-only-inline{cls}">{en}</span>'

# ---------- transliteration ----------
def prep_sanskrit(t):
    t = re.sub(r"(?<=[ಀ-೿]):", "ಃ", t)
    t = re.sub(r"(?<=[ಀ-೿])s(?=[ಀ-೿])", "ಽ", t)
    return t.replace("‌", "").replace("‍", "")
def translit_mantra(t):
    if not SC: return ""
    t = re.sub(r"[೦-೯]", "", prep_sanskrit(t))
    out = SC.transliterate(t, SC.KANNADA, SC.IAST).replace("ḻ", "ḷ").replace("//", " ‖").replace("/", " |")
    return re.sub(r"[ \t]+", " ", out).strip()
def translit_kn(t):
    return SC.transliterate(t.replace("‌", ""), SC.KANNADA, SC.ISO) if SC else ""
def verse_html(t):
    t = prep_sanskrit(t)
    t = re.sub(r"\s*//\s*", " ॥\n", t); t = re.sub(r"\s*/\s*", " ।\n", t)
    return "".join(f'<span class="vl">{esc(l.strip())}</span>' for l in t.split("\n") if l.strip())
def inline_md(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s); s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?![\w_])", r"<i>\1</i>", s)
    return s.replace("*", "")
def paras(t, md=False):
    out = []
    for p in re.split(r"\n", t or ""):
        p = p.strip()
        if not p or p == "---": continue
        out.append(f"<p>{inline_md(p) if md else esc(p)}</p>")
    return "".join(out)

# ---------- content ----------
entries = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((CONTENT / "entries").glob("*.json"))]
series = sorted(json.loads((CONTENT / "series.json").read_text(encoding="utf-8")), key=lambda s: s["start"])
SER = {s["key"]: s for s in series}
def series_for(date):
    cur = series[0]
    for s in series:
        if s["start"] <= date: cur = s
    return cur
for e in entries:
    e["col"] = COL_OF_TYPE.get(e["type"], COLS[0])
    if e["type"] in ("mantra", "note"): e["series"] = series_for(e["date"])["key"]
entries.sort(key=lambda e: (e["date"], e["time"]))
ORDER = {"note": 0, "mantra": 1, "poem": 2}
days = OrderedDict()
for e in entries: days.setdefault(e["date"], []).append(e)
for d in days: days[d].sort(key=lambda e: ORDER.get(e["type"], 5))
day_list = list(days)
daily = [d for d in day_list if any(e["type"] in ("mantra", "poem") for e in days[d])]
LATEST = daily[-1]
def by_type(t): return [e for e in entries if e["type"] == t]

# ---------- chrome ----------
NAV = [("index.html", "Home", "ಮುಖಪುಟ"), ("collections.html", "Collections", "ಸಂಗ್ರಹಗಳು"),
       ("archive.html", "Archive", "ದಿನಚರಿ"), ("about.html", "About", "ಪರಿಚಯ"), ("search.html", "Search", "ಹುಡುಕು")]
CUR = ' aria-current="page"'

def page(title, body, r="", active="", desc="", cls=""):
    nav = "".join(f'<a href="{r}{h}"{CUR if h == active else ""}>{bi(kn, en)}</a>' for h, en, kn in NAV)
    return f"""<!doctype html>
<html lang="en" data-lang="both">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc or SITE['tagline_en'])}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Akaya+Kanadaka&family=Marcellus+SC&family=Spectral:ital,wght@0,400;0,500;1,400&family=Tiro+Kannada:ital@0;1&display=swap">
<link rel="stylesheet" href="{r}assets/site.css">
<script>try{{var m=localStorage.getItem('vm-lang');if(m)document.documentElement.dataset.lang=m}}catch(e){{}}</script>
</head>
<body class="{cls}">
<div class="wrap">
<header class="mast">
  <a class="brand" href="{r}index.html" aria-label="{esc(SITE['name_en'])}, home">
    <span class="brand-kn" lang="kn">{SITE['name_kn']}</span>
    <span class="brand-en">{SITE['name_en']}</span>
  </a>
  <nav class="nav" aria-label="Sections">{nav}</nav>
  <div class="lang" role="group" aria-label="Language">
    <button type="button" data-set="kn" lang="kn">ಕನ್ನಡ</button><button type="button" data-set="both">Both</button><button type="button" data-set="en">English</button>
  </div>
</header>
<main>
{body}
</main>
<footer class="foot">
  <div class="foot-motto"><span lang="kn">{SITE['motto_kn']}</span> <span class="muted">· {SITE['motto_en']}</span></div>
  <p>Written in Kannada by {', '.join(f'<a href="{r}about.html#{k}">{esc(a["en"])}</a>' for k, a in AUTH.items())}. English renderings are AI-assisted drafts, reviewed by {esc(SITE['editor'])}; the Kannada is always the original.</p>
</footer>
</div>
<script src="{r}assets/site.js"></script>
</body>
</html>"""

def crumb(href, kn, en):
    return f'<nav class="crumb" aria-label="Back"><a href="{href}">← {bi(esc(kn), esc(en))}</a></nav>'

def pending(): return '<p class="pending">English translation is on its way.</p>'
def link(e, r): return f'{r}d/{e["date"]}.html#{e["id"]}'
def linked(t, e, r, mode): return t if mode == "full" else f'<a href="{link(e, r)}">{t}</a>'
def byline(e, r):
    a = AUTH[e["col"]["author"]]
    return f'<p class="byline"><a href="{r}about.html#{e["col"]["author"]}">{bi(esc(a["kn"]), esc(a["en"]))}</a></p>'

# ---------- renderers ----------
def mantra_head(e):
    s, n = SER[e["series"]], e["kn"].get("number")
    return (esc(s["kn"]) + (f" · ಮಂತ್ರ {kn_num(n)}" if n else ""), esc(s["en"]) + (f" · Mantra {n}" if n else ""))

def listen_links(s, r=""):
    if not s.get("listen"): return ""
    items = "".join(f'<a href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l["label"])} <span aria-hidden="true">↗</span></a>' for l in s["listen"])
    return f'<p class="listen"><span class="listen-label">{bi("ಪಠಣ ಕೇಳಿ", "Hear it chanted")}</span>{items}</p>'

def render_mantra(e, r, mode="full"):
    kn, en = e["kn"], e.get("en") or {}
    s = SER[e["series"]]; n = kn.get("number")
    hk, he = mantra_head(e)
    title = f'<a href="{link(e, r)}">{bi(hk, he)}</a>' if mode != "full" else bi(hk, he)
    tl = translit_mantra(kn["mantra"])
    o = [f'<article class="entry m-palm" id="{e["id"]}"><div class="leaf"><div class="leaf-in">',
         f'<p class="eyebrow">{bi(esc(e["col"]["kn"]), esc(e["col"]["en"]))} · <span class="ref">{esc(s["ref"])}</span></p>',
         f'<h2 class="e-title">{title}</h2>']
    if n: o.append(f'<span class="seal" aria-hidden="true" lang="kn">{kn_num(n)}</span>')
    if mode == "full" and (kn.get("meta") or en.get("meta")):
        o.append(f'<p class="meta kn-only" lang="kn">{esc(" · ".join(kn.get("meta", [])))}</p>')
        if en.get("meta"): o.append(f'<p class="meta en-only">{esc(en["meta"])}</p>')
    o.append(f'<div class="verse kn-only" lang="kn">{verse_html(kn["mantra"])}</div>')
    if tl: o.append(f'<p class="translit">{esc(tl)}</p>')
    if mode != "full":
        o.append(f'<div class="two"><div class="col kn-only" lang="kn">{paras(kn.get("bhavartha"))}</div>'
                 f'<div class="col en-only">{paras(en.get("meaning")) if en.get("meaning") else pending()}</div></div>')
        if mode == "home":
            o.append(f'<p class="more"><a href="{link(e, r)}">{bi("ಪ್ರತಿಪದಾರ್ಥ ಸಹಿತ ಓದಿ →", "Read it word by word →")}</a></p>')
        o.append('</div></div></article>'); return "\n".join(o)
    if kn.get("gloss") or en.get("gloss"):
        o.append(f'<section class="block"><h3 class="label">{bi("ಪ್ರತಿಪದಾರ್ಥ", "Word by word", " lbl")}</h3>')
        if en.get("gloss"):
            o.append('<dl class="gloss en-only">' + "".join(f'<div class="g-row"><dt>{esc(w)}</dt><dd>{esc(m)}</dd></div>' for w, m in en["gloss"]) + "</dl>")
        if kn.get("gloss"):
            kg = '<dl class="gloss" lang="kn">' + "".join(f'<div class="g-row"><dt>{esc(w)}</dt><dd>{esc(m)}</dd></div>' for w, m in kn["gloss"]) + "</dl>"
            if en.get("gloss"):
                o.append(f'<div class="only-both"><details class="kn-gloss"><summary lang="kn">ಕನ್ನಡ ಪ್ರತಿಪದಾರ್ಥ ತೋರಿಸು</summary>{kg}</details></div><div class="kn-alone">{kg}</div>')
            else:
                o.append(f'<div class="kn-only">{kg}</div>')
        o.append("</section>")
    o.append(f'<section class="block"><h3 class="label">{bi("ಭಾವಾರ್ಥ", "Meaning", " lbl")}</h3>'
             f'<div class="two"><div class="col kn-only" lang="kn">{paras(kn.get("bhavartha") or kn.get("vishesha"))}</div>'
             f'<div class="col en-only">{paras(en.get("meaning")) if en.get("meaning") else pending()}</div></div></section>')
    if kn.get("vishesha") and kn.get("bhavartha"):
        o.append(f'<section class="block"><h3 class="label">{bi("ವಿಶೇಷ", "Further notes", " lbl")}</h3><div class="two"><div class="col kn-only" lang="kn">{paras(kn["vishesha"])}</div>'
                 f'<div class="col en-only">{paras(en.get("vishesha"))}</div></div></section>')
    if en.get("note"): o.append(f'<p class="note en-only">{esc(en["note"])}</p>')
    o.append(listen_links(s))
    o.append(byline(e, r))
    o.append("</div></div></article>")
    return "\n".join(o)

def render_note(e, r, mode="full"):
    kn, en = e["kn"], e.get("en") or {}
    s = SER[e["series"]]
    t = bi(esc(kn.get("title") or "ಪೀಠಿಕೆ"), esc(en.get("title") or "An introduction"))
    o = [f'<article class="entry m-palm note" id="{e["id"]}"><div class="leaf"><div class="leaf-in">',
         f'<p class="eyebrow">{bi("ಪೀಠಿಕೆ", "Introduction")} · <span class="ref">{esc(s["en"])}</span></p>',
         f'<h2 class="e-title">{linked(t, e, r, mode)}</h2>']
    if mode == "full":
        o.append(f'<div class="two"><div class="col kn-only" lang="kn">{paras(kn["body"])}</div><div class="col en-only">{paras(en.get("body")) if en.get("body") else pending()}</div></div>')
        o.append(byline(e, r))
    o.append("</div></div></article>")
    return "\n".join(o)

def render_poem(e, r, mode="full"):
    kn, en = e["kn"], e.get("en") or {}
    d = D(e["date"])
    kd, ed = f'{kn_num(d.day)} {KN_MONTH[d.month-1]} {kn_num(d.year)}', f'{d.day} {d.strftime("%B %Y")}'
    theme = en.get("theme")
    t = bi(kd, esc(theme) if theme else ed)
    kl = "".join(f'<span class="vl">{esc(l)}</span>' for l in kn["lines"])
    tl = "".join(f'<span class="vl">{esc(translit_kn(l))}</span>' for l in kn["lines"]) if SC else ""
    el = "".join(f'<span class="vl">{esc(l)}</span>' for l in en.get("lines", []))
    o = [f'<article class="entry m-paper{" compact" if mode == "grid" else ""}" id="{e["id"]}"><div class="sheet-wrap"><div class="sheet">',
         f'<p class="eyebrow">{bi(esc(e["col"]["kn"]), esc(e["col"]["en"]))}' + (f' · <span class="ref en-only-inline">{ed}</span>' if theme else "") + '</p>',
         f'<h2 class="e-title">{linked(t, e, r, mode)}</h2>',
         '<div class="two poem">',
         f'<div class="col kn-only"><p class="stanza hand" lang="kn">{kl}</p></div>',
         '<div class="col en-only">' + (f'<p class="stanza tl en-alone">{tl}</p>' if tl else "")
         + (f'<p class="mini-label">Literal</p><p class="stanza stanza-en">{el}</p>' if el else pending()) + "</div></div>"]
    if en.get("bhavartha"):
        o.append(f'<div class="bhava en-only"><p class="mini-label">Bhāvārtha · <span class="theme">{esc(theme or "")}</span></p><p class="bhava-text">{esc(en["bhavartha"])}</p></div>')
    if mode != "grid":
        if kn.get("footnote"): o.append(f'<p class="note kn-only" lang="kn">{esc(kn["footnote"])}</p>')
        if en.get("note"): o.append(f'<p class="note en-only">{esc(en["note"])}</p>')
        o.append(byline(e, r))
    o.append("</div></div></article>")
    return "\n".join(o)

def render_dharma(e, r, mode="full"):
    kn, en = e["kn"], e.get("en") or {}
    t = bi(esc(kn.get("title")), esc(en.get("title") or kn.get("title")))
    o = [f'<article class="entry m-copper{" compact" if mode != "full" else ""}" id="{e["id"]}"><div class="plate"><span class="ring" aria-hidden="true"></span>',
         f'<p class="eyebrow">{bi(esc(e["col"]["kn"]), esc(e["col"]["en"]))} · <span class="ref">{en_short(D(e["date"]))}</span></p>',
         f'<h2 class="e-title">{linked(t, e, r, mode)}</h2>']
    if mode == "full":
        o.append(f'<div class="two"><div class="col kn-only" lang="kn">{paras(kn["body"], md=True)}</div>'
                 f'<div class="col en-only">{paras(en.get("body"), md=True) if en.get("body") else pending()}</div></div>')
        if en.get("note"): o.append(f'<p class="note en-only">{esc(en["note"])}</p>')
        o.append(byline(e, r))
    else:
        first_en = (en.get("body") or "").split("\n")[0]
        first_kn = kn["body"].split("\n")[0]
        cut = lambda s, n: (s[:n].rsplit(" ", 1)[0] + "…") if len(s) > n else s
        o.append(f'<p class="teaser kn-only" lang="kn">{esc(cut(re.sub(r"[*_]", "", first_kn), 150))}</p>')
        if first_en: o.append(f'<p class="teaser en-only">{esc(cut(first_en, 170))}</p>')
        o.append(f'<p class="more"><a href="{link(e, r)}">{bi("ಪೂರ್ತಿ ಓದಿ →", "Read the whole plate →")}</a></p>')
    o.append("</div></article>")
    return "\n".join(o)

RENDER = {"mantra": render_mantra, "note": render_note, "poem": render_poem, "dharma": render_dharma}
def render(e, r, mode="full"): return RENDER.get(e["type"], render_note)(e, r, mode)

# ---------- shared pieces ----------
def day_head(date, r, prev=None, nxt=None):
    d = D(date)
    pn = '<nav class="daynav" aria-label="Other days">'
    pn += f'<a href="{r}d/{prev}.html" rel="prev">← {bi("ಹಿಂದಿನ ದಿನ", esc(en_date(D(prev), False)))}</a>' if prev else "<span></span>"
    pn += f'<a href="{r}d/{nxt}.html" rel="next">{bi("ಮುಂದಿನ ದಿನ", esc(en_date(D(nxt), False)))} →</a>' if nxt else "<span></span>"
    return f'<div class="dayhead"><p class="date-kn" lang="kn">{kn_date(d)}</p><p class="date-en">{en_date(d)}</p></div>{pn}</nav>'

def progress(key, r):
    s = SER[key]; total = s.get("verses")
    ms = [e for e in entries if e["type"] == "mantra" and e.get("series") == key]
    nums = {e["kn"]["number"] for e in ms if e["kn"].get("number")}
    if not total: return ""
    ticks = "".join(f'<i class="{"on" if i + 1 in nums else ""}"></i>' for i in range(total))
    return (f'<div class="progress"><p class="p-label">{bi(f"{kn_num(total)} ಮಂತ್ರಗಳಲ್ಲಿ {kn_num(len(nums))}", f"{len(nums)} of {total} mantras so far")}</p>'
            f'<span class="ticks" aria-hidden="true">{ticks}</span></div>')

def portrait(key, r, size=""):
    a = AUTH[key]
    inner = f'<img src="{r}{esc(a["photo"])}" alt="{esc(a["en"])}">' if a.get("photo") else f'<span class="initial" lang="kn">{a["initial"]}</span>'
    mat = next(c["material"] for c in COLS if c["author"] == key)
    return f'<span class="portrait p-{mat} {size}">{inner}</span>'

def medallion(c, r, size=""):
    if not c.get("image"): return ""
    return (f'<figure class="medal m-{c.get("image_shape", "round")} {size}"><img src="{r}{c["image"]}" alt="{esc(c["image_en"])}" loading="lazy">'
            f'<figcaption>{bi(esc(c["image_kn"]), esc(c["image_en"]))}</figcaption></figure>')

def more_voices(r, big=False):
    return (f'<aside class="more-voices{" big" if big else ""}"><span class="mv-mark" aria-hidden="true" lang="kn">ಶ್ರೀ</span><div>'
            f'<p class="mv-title">{bi("ಇನ್ನಷ್ಟು ಧ್ವನಿಗಳು ಬರಲಿವೆ", "More voices are on their way")}</p>'
            f'<p class="mv-text">{bi("ವೈದಿಕ ಮಿತ್ರರು ಬಳಗದಲ್ಲಿ ಅನೇಕ ವಿದ್ವಾಂಸರು ಮತ್ತು ಉಪಾಸಕರಿದ್ದಾರೆ. ಅವರ ಬರಹಗಳು ಮತ್ತು ಬೋಧನೆಗಳು ಮುಂದೆ ಇಲ್ಲಿ ಒಂದೊಂದಾಗಿ ಸೇರಲಿವೆ. ಇದು ಆರಂಭ ಮಾತ್ರ.", "The Vaidika Mitraru circle is home to many Vedic scholars and practitioners. Their writing and teaching will be added here, one collection at a time. These three are only the beginning.")}</p>'
            f'</div></aside>')

def col_card(c, r):
    items = [e for e in entries if e["type"] in c["types"]]
    first, last = items[0]["date"], items[-1]["date"]
    a = AUTH[c["author"]]
    img = f'<img class="shelf-medal" src="{r}{c["image"]}" alt="" loading="lazy">' if c.get("image") else ""
    return (f'<a class="shelf s-{c["material"]}" href="{r}{c["page"]}"><span class="swatch" aria-hidden="true">{img}</span>'
            f'<span class="shelf-body"><span class="shelf-kn" lang="kn">{esc(c["kn"])}</span><span class="shelf-en">{esc(c["en"])}</span>'
            f'<span class="shelf-sub">{bi(esc(c["sub_kn"]), esc(c["sub_en"]))}</span>'
            f'<span class="shelf-meta">{esc(a["en"])} · {len(items)} posts · {esc(c["cadence_en"])}</span></span></a>')

# ---------- build ----------
def write(path, text):
    p = OUT / path; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8")

def build():
    if OUT.exists(): shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)
    for f in STATIC.iterdir():
        if f.is_file(): shutil.copy(f, OUT / "assets" / f.name)
        elif f.is_dir(): shutil.copytree(f, OUT / "assets" / f.name)

    # --- day pages
    for i, date in enumerate(day_list):
        body = day_head(date, "../", day_list[i-1] if i else None, day_list[i+1] if i + 1 < len(day_list) else None)
        body += '<div class="flow">' + "".join(render(e, "../") for e in days[date]) + "</div>"
        write(f"d/{date}.html", page(f"{en_date(D(date), False)} · {SITE['name_en']}", body, "../"))

    # --- home
    today = days[LATEST]
    m = next((e for e in today if e["type"] == "mantra"), None)
    p = next((e for e in today if e["type"] == "poem"), None)
    dharmas = by_type("dharma")
    feat = dharmas[D(LATEST).toordinal() % len(dharmas)] if dharmas else None
    d = D(LATEST)
    deity = SITE.get("deity_image")
    niche = (f'<img src="{deity}" alt="Śrī Rājaśyāmalā, goddess of learning and eloquence">' if deity else
             '<span class="niche-ph"><span class="niche-shri" lang="kn">ಶ್ರೀ</span><span class="niche-note">Image of Sarasvatī<br>to be placed here</span></span>')
    steps = [
      ("ಶ್ರುತಿ", "Śruti", "What is heard", "palm",
       "ವೇದ ಬರವಣಿಗೆಗಿಂತ ಮೊದಲು ಕೇಳಲ್ಪಟ್ಟದ್ದು. ಸಾವಿರಾರು ವರ್ಷಗಳ ಕಾಲ ಪಠಣದ ಮೂಲಕವೇ ಅದರ ಮಂತ್ರಗಳು ಉಳಿದುಬಂದಿವೆ.",
       "The Veda was heard long before it was written. Its mantras have been kept alive for millennia by recitation, sound by sound."),
      ("ಭಾಷ್ಯ", "Bhāṣya", "What is understood", "palm",
       "ಪಠಣ ಶಬ್ದವನ್ನು ಕಾಪಾಡುತ್ತದೆ; ಭಾಷ್ಯ ಅರ್ಥವನ್ನು ತೆರೆಯುತ್ತದೆ. ಸಾಯಣರ ಭಾಷ್ಯವನ್ನು ಪದಪದವಾಗಿ ಅನುಸರಿಸಿದಾಗ, ಬಾಯಿಪಾಠವಾದ ಮಂತ್ರ ಅರಿವಾಗುತ್ತದೆ.",
       "Recitation keeps the sound; the commentary opens the sense. Followed word by word through Sāyaṇa, a chant known by heart becomes something understood."),
      ("ಅನುಭವ", "Anubhava", "What is lived", "copper",
       "ಅರಿವು ಪುಟದಲ್ಲೇ ಉಳಿಯುವುದಿಲ್ಲ. ಹೇಗೆ ಊಟ ಮಾಡಬೇಕು, ಯಾವಾಗ ಆಹುತಿ ಕೊಡಬೇಕು, ಆಚಾರವನ್ನು ಏಕೆ ಪಾಲಿಸಬೇಕು ಎಂಬುದರಲ್ಲಿ ಅದು ಕಾಣುತ್ತದೆ. ಜ್ಞಾನ ದಿನನಿತ್ಯದ ಬದುಕಾಗುತ್ತದೆ.",
       "Understanding does not stay on the page. It shows in how we eat, when we let an offering fall, which custom we keep and why. Knowledge becomes the texture of an ordinary day."),
      ("ಕಾವ್ಯ", "Kāvya", "What is sung", "paper",
       "ಆ ಅರಿವಿನಿಂದ ಬಾಳಿದ ಬದುಕು ತನ್ನದೇ ಮಾತಿನಲ್ಲಿ ಹೊರಹೊಮ್ಮುತ್ತದೆ: ನಮ್ಮೆಲ್ಲರೊಳಗಿನ ಮೂಢಮನುಜನಿಗೆ ಸೂರ್ಯೋದಯದ ನಾಲ್ಕು ಸಾಲುಗಳು.",
       "And a life lived with that understanding speaks back in its own words: four lines at sunrise, addressed to the deluded one in each of us."),
    ]
    step_html = "".join(
        f'<li class="step st-{mat}"><span class="step-n" aria-hidden="true">{kn_num(i + 1)}</span>'
        f'<p class="step-kn" lang="kn">{k}</p><p class="step-en">{e} <span>· {sub}</span></p>'
        f'<p class="step-text">{bi(tk, te)}</p></li>'
        for i, (k, e, sub, mat, tk, te) in enumerate(steps))
    body = f"""<section class="hero">
  <figure class="niche">
    <div class="arch">{niche}</div>
    <figcaption>
      <p class="niche-name">{bi("ಶ್ರೀ ರಾಜಶ್ಯಾಮಲಾ", "Śrī Rājaśyāmalā")}</p>
      <p class="inv" lang="kn">ಮಾಣಿಕ್ಯವೀಣಾಮುಪಲಾಲಯಂತೀಂ ಮದಾಲಸಾಂ ಮಂಜುಳವಾಗ್ವಿಲಾಸಾಮ್ ।<br>ಮಾಹೇಂದ್ರನೀಲದ್ಯುತಿಕೋಮಲಾಂಗೀಂ ಮಾತಂಗಕನ್ಯಾಂ ಮನಸಾ ಸ್ಮರಾಮಿ ॥</p>
      <p class="inv-en">I hold in my mind Mātaṅga’s daughter, gently playing her jewelled vīṇā, languid with joy, graceful in speech, her tender form glowing like sapphire. <span class="muted">— Śyāmalā Daṇḍakam</span></p>
    </figcaption>
  </figure>
  <div class="hero-text">
    <p class="motto" lang="kn">{SITE['motto_kn']}</p>
    <p class="motto-tl">{SITE['motto_tl']}</p>
    <p class="motto-en">“{SITE['motto_en']}” <span class="muted">— {SITE['motto_src']}</span></p>
    <p class="hero-lede">{bi("ಪ್ರತಿದಿನ ಒಂದು ವೇದಮಂತ್ರದ ಅರ್ಥ, ಒಂದು ನಾಲ್ಕು ಸಾಲಿನ ಪದ್ಯ, ಮತ್ತು ಆಗಾಗ ಧರ್ಮಶಾಸ್ತ್ರದ ಸೂಕ್ಷ್ಮ ವಿಷಯಗಳು. ಮೂವರು ಮಿತ್ರರ ಸ್ವಾಧ್ಯಾಯ, ಕನ್ನಡದಲ್ಲಿ; ಇಂಗ್ಲಿಷ್ ಅನುವಾದದೊಂದಿಗೆ.",
     "Every morning, the meaning of one Veda mantra and a four-line verse to sit with; now and then, a fine point of dharma. The daily study of three friends, written in Kannada, with English alongside.")}</p>
  </div>
</section>
<section class="prelude">
  <h2 class="sec-h">{bi("ಅರ್ಥವನ್ನು ಏಕೆ ತಿಳಿಯಬೇಕು?", "Why learn the meaning?")}</h2>
  <blockquote class="nirukta">
    <p lang="kn">ಸ್ಥಾಣುರಯಂ ಭಾರಹಾರಃ ಕಿಲಾಭೂದ್ ಅಧೀತ್ಯ ವೇದಂ ನ ವಿಜಾನಾತಿ ಯೋಽರ್ಥಮ್ ।<br>ಯೋಽರ್ಥಜ್ಞ ಇತ್ ಸಕಲಂ ಭದ್ರಮಶ್ನುತೇ ನಾಕಮೇತಿ ಜ್ಞಾನವಿಧೂತಪಾಪ್ಮಾ ॥</p>
    <p class="nk-en">“One who learns the Veda by heart but does not know its meaning is like a post that merely bears a load. One who knows the meaning gains every good, and, his faults shaken off by knowledge, reaches the highest world.”</p>
    <p class="nk-src">Yāska, <i>Nirukta</i> 1.18</p>
  </blockquote>
  <p class="prelude-lede">{bi("ಈ ತಾಣದ ಮೂರು ಸಂಗ್ರಹಗಳು ಒಂದೇ ದಾರಿಯ ಹೆಜ್ಜೆಗಳು: ಕೇಳಿದ್ದು ಅರ್ಥವಾಗಿ, ಅರ್ಥವಾದದ್ದು ಬದುಕಾಗಿ, ಬದುಕಿದ್ದು ಕಾವ್ಯವಾಗಿ ಹರಿಯುತ್ತದೆ.",
     "The three collections here are steps along one path. What is heard becomes understood; what is understood is lived; and what is lived pours out as poetry.")}</p>
  <ol class="steps">{step_html}</ol>
</section>
<section class="today">
  <h2 class="sec-h"><span class="sec-kn" lang="kn">ಇಂದು · {kn_date(d, False)}</span><span class="sec-en">Today · {en_date(d)}</span></h2>
  <div class="today-grid">
    {render(m, "", "home") if m else ""}
    {render(p, "", "home") if p else ""}
  </div>
</section>"""
    cur = m["series"] if m else None
    side = ""
    if cur:
        s = SER[cur]
        side += (f'<div class="reading"><h2 class="sec-h small">{bi("ಈಗ ಓದುತ್ತಿರುವ ಸೂಕ್ತ", "Now reading")}</h2>'
                 f'<a class="reading-title" href="s/{cur}.html"><span lang="kn">{esc(s["kn"])}</span><span class="rt-en">{esc(s["en"])} · {esc(s["ref"])}</span></a>'
                 f'{progress(cur, "")}<p class="reading-about">{esc(s.get("about", ""))}</p>{listen_links(s)}</div>')
    if feat:
        side += f'<div class="featured"><h2 class="sec-h small">{bi("ಧರ್ಮಸೂಕ್ಷ್ಮದಿಂದ", "From the Dharma Sūkṣma")}</h2>{render(feat, "", "teaser")}</div>'
    body += f'<section class="pair">{side}</section>'
    voices = "".join(f'<a class="voice" href="about.html#{k}">{portrait(k, "")}<span class="v-name">{bi(esc(a["kn"]), esc(a["en"]))}</span>'
                     f'<span class="v-role">{bi(esc(a["role_kn"]), esc(a["role_en"]))}</span></a>' for k, a in AUTH.items())
    body += f'<section class="voices"><h2 class="sec-h">{bi("ಬರೆಯುವವರು", "The voices")}</h2><div class="voice-row">{voices}</div>{more_voices("")}</section>'
    body += (f'<section class="shelves"><h2 class="sec-h">{bi("ಸಂಗ್ರಹಗಳು", "Collections")}</h2><div class="shelf-grid">'
             + "".join(col_card(c, "") for c in COLS) + "</div></section>")
    week = [x for x in daily[-8:-1]][::-1]
    if week:
        li = ""
        for wd in week:
            wm = next((e for e in days[wd] if e["type"] == "mantra"), None)
            wp = next((e for e in days[wd] if e["type"] == "poem"), None)
            ml = bi(*mantra_head(wm)) if wm else ""
            pl = esc((wp.get("en") or {}).get("lines", [wp["kn"]["lines"][0]])[0]) if wp else ""
            li += f'<li><a href="d/{wd}.html"><span class="w-date">{D(wd).strftime("%a %d %b")}</span><span class="w-m">{ml}</span><span class="w-p">{pl}</span></a></li>'
        body += f'<section class="week"><h2 class="sec-h">{bi("ಈ ವಾರ", "Earlier this week")}</h2><ul class="weeklist">{li}</ul></section>'
    write("index.html", page(SITE["name_en"], body, "", "index.html", cls="home"))

    # --- collections
    body = (f'<div class="pagehead"><h1>{bi("ಸಂಗ್ರಹಗಳು", "Collections")}</h1>'
            '<p class="lede">Each collection is one person’s steady practice, and each is set on its own material: the Veda on palm leaf, the verses on handmade paper, the rules of dharma on copper plate, the way such things were once kept.</p></div>'
            '<div class="shelf-grid wide">' + "".join(col_card(c, "") for c in COLS) +
            '</div>' + more_voices("", True))
    write("collections.html", page(f"Collections · {SITE['name_en']}", body, "", "collections.html"))

    # --- mantras + series
    cards = ""
    for s in reversed(series):
        ms = [e for e in entries if e.get("series") == s["key"] and e["type"] == "mantra"]
        if not ms: continue
        cards += (f'<li><a class="s-card" href="s/{s["key"]}.html"><span class="s-kn" lang="kn">{esc(s["kn"])}</span><span class="s-en">{esc(s["en"])}</span>'
                  f'<span class="s-ref">{esc(s["ref"])}</span><span class="s-count">{len(ms)} posts · {D(ms[0]["date"]).strftime("%d %b")} – {D(ms[-1]["date"]).strftime("%d %b %Y")}</span></a></li>')
        rows = "".join(render(e, "../", "list") for e in entries if e.get("series") == s["key"])
        sb = (crumb("../mantras.html", COLS[0]["kn"], COLS[0]["en"]) + f'<div class="pagehead"><p class="eyebrow">{esc(s["ref"])}</p><h1>{bi(esc(s["kn"]), esc(s["en"]))}</h1>'
              + (f'<p class="lede">{esc(s["about"])}</p>' if s.get("about") else "") + f'{listen_links(s)}</div>'
              f'{progress(s["key"], "../")}<div class="flow bound">{rows}</div>')
        write(f"s/{s['key']}.html", page(f"{s['en']} · {SITE['name_en']}", sb, "../", "collections.html"))
    c = COLS[0]
    body = (crumb("collections.html", "ಸಂಗ್ರಹಗಳು", "Collections") + f'<div class="pagehead has-medal">{medallion(c, "")}<p class="eyebrow">{bi(esc(AUTH[c["author"]]["kn"]), esc(AUTH[c["author"]]["en"]))}</p><h1>{bi(esc(c["kn"]), esc(c["en"]))}</h1>'
            f'<p class="lede">Each morning, usually well before five, Sri Hari posts one mantra: the verse as it is recited, its meaning word by word, and then its sense as a whole, following Sāyaṇa’s commentary. He moves through whole hymns, one verse a day. Each hymn links to a traditional recitation on the Vedic Heritage Portal.</p></div>'
            f'<ul class="s-grid">{cards}</ul>')
    write("mantras.html", page(f"{c['en']} · {SITE['name_en']}", body, "", "collections.html"))

    # --- verses
    c = COLS[1]
    poems = sorted(by_type("poem"), key=lambda e: e["date"], reverse=True)
    months = OrderedDict()
    for x in poems: months.setdefault(x["date"][:7], []).append(x)
    body = (crumb("collections.html", "ಸಂಗ್ರಹಗಳು", "Collections") + f'<div class="pagehead has-medal">{medallion(c, "")}<p class="eyebrow">{bi(esc(AUTH[c["author"]]["kn"]), esc(AUTH[c["author"]]["en"]))}</p><h1>{bi(esc(c["kn"]), esc(c["en"]))}</h1>'
            '<p class="lede">Four lines each morning, each ending with the same address, <i lang="kn">ಮೂಢಮನುಜ</i>: “O deluded one”. Like the old Kannada <i>kagga</i>, every line shares the consonant of its second syllable (<i>ādiprāsa</i>).</p>'
            f'<p class="count">{len(poems)} verses</p></div><nav class="jump" aria-label="Months">'
            + " ".join(f'<a href="#m{k}">{D(k + "-01").strftime("%b %Y")}</a>' for k in months) + "</nav>")
    for k, ps in months.items():
        body += f'<h2 class="sec-h" id="m{k}">{D(k + "-01").strftime("%B %Y")}</h2><div class="paper-grid">' + "".join(render(x, "", "grid") for x in ps) + "</div>"
    write("verses.html", page(f"{c['en']} · {SITE['name_en']}", body, "", "collections.html"))

    # --- dharma
    c = COLS[2]
    ds = sorted(dharmas, key=lambda e: e["date"], reverse=True)
    body = (crumb("collections.html", "ಸಂಗ್ರಹಗಳು", "Collections") + f'<div class="pagehead has-medal">{medallion(c, "")}<p class="eyebrow">{bi(esc(AUTH[c["author"]]["kn"]), esc(AUTH[c["author"]]["en"]))}</p><h1>{bi(esc(c["kn"]), esc(c["en"]))}</h1>'
            '<p class="lede">The fine points: when exactly the oblation should fall, how many times to sound the conch, why a custom is kept and whether the śāstra requires it. Manjunatha Shastri shares these from the dharmaśāstra, the muhūrta texts and the practice of the Śṛṅgeri tradition. They arrive when a question calls for them, not on a schedule.</p>'
            f'<p class="count">{len(ds)} plates</p></div><div class="plate-grid">' + "".join(render(x, "", "teaser") for x in ds) + "</div>")
    write("dharma.html", page(f"{c['en']} · {SITE['name_en']}", body, "", "collections.html"))

    # --- archive
    body = (f'<div class="pagehead"><h1>{bi("ದಿನಚರಿ", "Archive")}</h1><p class="lede">Every day with a post, month by month. Each mark shows what arrived that day.</p>'
            '<p class="legend"><span><i class="k-palm"></i>Mantra</span><span><i class="k-paper"></i>Verse</span><span><i class="k-copper"></i>Dharma</span></p></div>')
    months = OrderedDict()
    for dd in day_list: months.setdefault(dd[:7], []).append(dd)
    for k in reversed(list(months)):
        first = D(k + "-01"); nxt = (first.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        cells = "".join('<span class="cal-pad"></span>' for _ in range(first.weekday()))
        x = first
        while x < nxt:
            iso = x.isoformat()
            if iso in days:
                marks = "".join(f'<i class="k-{COL_OF_TYPE[t]["material"]}"></i>' for t in dict.fromkeys(e["type"] for e in days[iso] if e["type"] != "note"))
                cells += f'<a class="cal-d" href="d/{iso}.html" title="{en_date(x, False)}"><span>{x.day}</span><span class="marks">{marks}</span></a>'
            else:
                cells += f'<span class="cal-d none"><span>{x.day}</span></span>'
            x += datetime.timedelta(days=1)
        body += (f'<section class="cal"><h2 class="sec-h">{first.strftime("%B %Y")} <span lang="kn" class="kn-sub">{KN_MONTH[first.month-1]}</span></h2>'
                 '<div class="cal-grid">' + "".join(f'<span class="cal-w">{w}</span>' for w in "MTWTFSS") + f"{cells}</div></section>")
    write("archive.html", page(f"Archive · {SITE['name_en']}", body, "", "archive.html"))

    # --- search
    idx = []
    for e in entries:
        en = e.get("en") or {}
        if e["type"] == "poem": k, t, l = " ".join(e["kn"]["lines"]), " ".join(en.get("lines", [])), "Mūḍha Manuja"
        elif e["type"] == "mantra":
            k, t = e["kn"]["mantra"] + " " + (e["kn"].get("bhavartha") or ""), en.get("meaning", "")
            l = mantra_head(e)[1]
        else: k, t, l = (e["kn"].get("title") or "") + " " + e["kn"]["body"], (en.get("title", "") + " " + en.get("body", "")), e["col"]["en"]
        idx.append({"u": link(e, ""), "d": e["date"], "l": html.unescape(l), "k": re.sub(r"[*_]", "", k)[:600], "e": t[:600],
                    "r": translit_mantra(e["kn"]["mantra"])[:300] if e["type"] == "mantra" else ""})
    write("search-index.json", json.dumps(idx, ensure_ascii=False, separators=(",", ":")))
    body = (f'<div class="pagehead"><h1>{bi("ಹುಡುಕು", "Search")}</h1><p class="lede">Search in Kannada, English or romanized Sanskrit, for example <i lang="kn">ಅಗ್ನಿ</i>, <i>patience</i> or <i>soma</i>.</p></div>'
            '<form class="search" id="search-form" role="search"><label for="q" class="sr">Search</label><input id="q" name="q" type="search" placeholder="ಅಗ್ನಿ, patience, oṣadhī …" autocomplete="off"></form>'
            '<p class="muted" id="search-status" aria-live="polite"></p><ol class="results" id="results"></ol>')
    write("search.html", page(f"Search · {SITE['name_en']}", body, "", "search.html"))

    # --- about
    write("about.html", page(f"About · {SITE['name_en']}", about(), "", "about.html", cls="about"))
    print(f"built {len(day_list)} days, {len(entries)} entries → {OUT}")

def about_charts():
    """Two small infographics for the About page, drawn as inline SVG at build time."""
    def mins(e): h, m = map(int, e["time"].split(":")); return h * 60 + m
    lo, hi = 120, 540  # 2:00 to 9:00
    W, L, R = 760, 120, 20
    x = lambda t: L + (t - lo) / (hi - lo) * (W - L - R)
    rows = [("mantra", "Sri Hari", "mantras", "viz1"), ("poem", "Kusha N M", "verses", "viz2")]
    H = 70 + 84 * len(rows)
    g = [f'<rect class="dawn" x="{x(355):.1f}" y="24" width="{x(400) - x(355):.1f}" height="{H - 58}" rx="4"/>',
         f'<text class="ax" x="{(x(355) + x(400)) / 2:.1f}" y="18" text-anchor="middle">sunrise in Karnataka</text>']
    for hr in range(2, 10):
        t = hr * 60
        g.append(f'<line class="grid" x1="{x(t):.1f}" x2="{x(t):.1f}" y1="24" y2="{H - 34}"/>')
        g.append(f'<text class="ax" x="{x(t):.1f}" y="{H - 16}" text-anchor="middle">{hr}:00</text>')
    hidden = 0
    for i, (typ, name, noun, cls) in enumerate(rows):
        es = [e for e in entries if e["type"] == typ]
        ts = sorted(mins(e) for e in es)
        med = ts[len(ts) // 2]
        cy = 74 + i * 84
        g.append(f'<text class="rl" x="{L - 14}" y="{cy - 4}" text-anchor="end">{name}</text><text class="rs" x="{L - 14}" y="{cy + 14}" text-anchor="end">{len(es)} {noun}</text>')
        for j, e in enumerate(es):
            t = mins(e)
            if not lo <= t <= hi: hidden += 1; continue
            jit = ((j * 37) % 29 - 14) * 1.1
            g.append(f'<circle class="{cls}" cx="{x(t):.1f}" cy="{cy + jit:.1f}" r="3.2"><title>{name}, {en_short(D(e["date"]))}, {e["time"]}</title></circle>')
        g.append(f'<line class="med" x1="{x(med):.1f}" x2="{x(med):.1f}" y1="{cy - 34}" y2="{cy + 20}"/>'
                 f'<text class="ml" x="{x(med) + 6:.1f}" y="{cy - 24}">usually {med // 60}:{med % 60:02d} am</text>')
    f1 = (f'<figure class="viz"><figcaption><b>When the posts arrive.</b> Each dot is one post, placed by the time it reached the group. '
          f'The mantras come before first light; the verses around sunrise.{f" ({hidden} posts outside 2–9 am are not shown.)" if hidden else ""}</figcaption>'
          f'<div class="viz-scroll"><svg viewBox="0 0 {W} {H}" role="img" aria-label="Posting times: Sri Hari usually around 4:20 am, Kusha around 6 am">{"".join(g)}</svg></div></figure>')
    # hymn timeline
    ser = [s for s in series if any(e.get("series") == s["key"] and e["type"] == "mantra" for e in entries)]
    d0, d1 = D("2025-11-01"), D(LATEST) + datetime.timedelta(days=5)
    L2, W2 = 190, 760
    xd = lambda d: L2 + (d - d0).days / (d1 - d0).days * (W2 - L2 - 70)
    rh = 24; H2 = 40 + rh * len(ser)
    g = []
    m = d0
    while m <= d1:
        g.append(f'<line class="grid" x1="{xd(m):.1f}" x2="{xd(m):.1f}" y1="10" y2="{H2 - 24}"/><text class="ax" x="{xd(m) + 3:.1f}" y="{H2 - 8}">{m.strftime("%b")}</text>')
        m = (m.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    rows_t = ""
    for i, s in enumerate(ser):
        ms = sorted([e for e in entries if e.get("series") == s["key"] and e["type"] == "mantra"], key=lambda e: e["date"])
        a, b = D(ms[0]["date"]), D(ms[-1]["date"]) + datetime.timedelta(days=1)
        y = 14 + i * rh
        g.append(f'<text class="rl sm" x="{L2 - 10}" y="{y + 12}" text-anchor="end">{esc(s["en"])}</text>'
                 f'<rect class="bar" x="{xd(a):.1f}" y="{y + 2}" width="{max(4, xd(b) - xd(a)):.1f}" height="{rh - 8}" rx="4"><title>{esc(s["en"])} ({esc(s["ref"])}): {len(ms)} posts, {en_short(a)} to {en_short(D(ms[-1]["date"]))}</title></rect>'
                 f'<text class="rs" x="{xd(b) + 6:.1f}" y="{y + 12}">{len(ms)}</text>')
        rows_t += f'<tr><td>{esc(s["en"])}</td><td>{esc(s["ref"])}</td><td>{en_short(a)}</td><td>{en_short(D(ms[-1]["date"]))}</td><td>{len(ms)}</td></tr>'
    f2 = (f'<figure class="viz"><figcaption><b>A year inside the Ṛgveda.</b> Each bar is one hymn, from the day Sri Hari began it to the day he finished; the number is how many posts it took.</figcaption>'
          f'<div class="viz-scroll"><svg viewBox="0 0 {W2} {H2}" role="img" aria-label="Timeline of the hymns Sri Hari has explained, November 2025 to now">{"".join(g)}</svg></div>'
          f'<details class="viz-table"><summary>Show as a table</summary><table><thead><tr><th>Hymn</th><th>Source</th><th>Began</th><th>Last post</th><th>Posts</th></tr></thead><tbody>{rows_t}</tbody></table></details></figure>')
    n = {t: len(by_type(t)) for t in ("mantra", "poem", "dharma")}
    stats = (f'<div class="stats"><div><b>{len(day_list)}</b><span>days with a post</span></div><div><b>{n["mantra"]}</b><span>mantras explained</span></div>'
             f'<div><b>{len(ser)}</b><span>hymns</span></div><div><b>{n["poem"]}</b><span>verses</span></div><div><b>{n["dharma"]}</b><span>copper plates</span></div></div>')
    return stats, f1, f2

def about():
    n = {t: len(by_type(t)) for t in ("mantra", "poem", "dharma")}
    first_poem = next(e for e in by_type("poem"))
    stats, f1, f2 = about_charts()
    fp = render_poem(first_poem, "", "grid")
    return f"""
<header class="about-head">
  <p class="eyebrow">{bi("ಪರಿಚಯ", "About")}</p>
  <h1 class="about-title"><span lang="kn">ಸ್ವಾಧ್ಯಾಯ</span> <span class="about-title-en">is the study you keep up on your own, every day, for its own sake.</span></h1>
  <blockquote class="epigraph">
    <p lang="kn">ಆಚಾರ್ಯಾತ್ ಪಾದಮಾದತ್ತೇ ಪಾದಂ ಶಿಷ್ಯಃ ಸ್ವಮೇಧಯಾ ।<br>ಪಾದಂ ಸಬ್ರಹ್ಮಚಾರಿಭ್ಯಃ ಪಾದಂ ಕಾಲಕ್ರಮೇಣ ಹಿ ॥</p>
    <p class="ep-en">A quarter of what we know comes from the teacher, a quarter from our own thinking, a quarter from those who study beside us, and the last quarter only with time.</p>
  </blockquote>
  <p class="lede big">This site gathers three such daily practices. They are written in Kannada by three friends who belong to the same circle, and they are set here with English alongside, so that more people can read along.</p>
</header>

<section class="story">
  <p class="story-date"><span lang="kn">೧೮ ನವೆಂಬರ್ ೨೦೨೫</span> · 18 November 2025</p>
  <h2>One afternoon in November</h2>
  <div class="story-body">
    <p>For about a week, Sri Hari had been posting a Veda mantra with its meaning every morning. That Tuesday a friend thanked him warmly, then asked a hard question: how do these meanings relate to the mantras we actually use in pūjā?</p>
    <p>Sri Hari’s reply set the tone for everything that followed.</p>
    <figure class="quote q-palm"><blockquote lang="kn">ನಾನು ಗುರು ಮುಖೇನ ಸಮಗ್ರವಾಗಿ ವೇದವನ್ನಾಗಲಿ, ಭಾಷ್ಯವನ್ನಾಗಲಿ ಕಲಿತವನಲ್ಲ. ವಯಕ್ತಿಯ ಆಸಕ್ತಿಯಿಂದ … ನಿಮ್ಮಲ್ಲಿ ಹಂಚಿಕೊಳ್ಳುತ್ತಿದ್ದೇನೆಯೇ ಹೊರತು ಪಾಂಡಿತ್ಯ ಪ್ರದರ್ಶನಕ್ಕೆ ಅಲ್ಲ.</blockquote>
      <figcaption>“I have not learned the Veda, or its commentaries, in full at a teacher’s feet. I share what I find out of personal interest, not to display learning. It is best, the elders say, to learn from teachers, from classmates, from one’s own experience, and from discussion, not from argument.” <span class="who">— Sri Hari</span></figcaption></figure>
    <p>A few minutes later Kusha answered him with the verse at the top of this page, about the four quarters of learning. Then he wrote:</p>
    <figure class="quote q-paper"><blockquote lang="kn">ಎಲ್ಲಕ್ಕೂ ಆಸಕ್ತಿಯೇ ಮುಖ್ಯ… ತಮ್ಮ ಕಾರ್ಯ ಇನ್ನೂ ಅನೇಕರ ಮನದ ಜ್ಯೋತಿಗಳನ್ನು ಬೆಳಗುವಂತಾಗಲಿ.</blockquote>
      <figcaption>“Interest is what matters most. It was the same for the seers of old: many of the Veda’s mantras are the fruit of deep study driven by curiosity. May your work go on lighting the lamps in many more minds.” <span class="who">— Kusha N M</span></figcaption></figure>
    <p>Forty minutes later Kusha posted four lines ending in <i lang="kn">ಮೂಢಮನುಜ</i>. It was his first. Half an hour after that he told Sri Hari that, like Hanumān, he simply did not know his own strength. Kusha has written a verse nearly every morning since.</p>
    <div class="first-verse">{fp}</div>
  </div>
</section>

<section class="people">
  <h2 class="sec-h">{bi("ಬರೆಯುವವರು", "The voices")}</h2>
  <article class="person" id="sri-hari">
    {portrait("sri-hari", "", "lg")}
    <div class="person-body">
      <p class="eyebrow">{bi("ಮಂತ್ರಾರ್ಥ", "Mantrārtha")} · on palm leaf</p>
      <h3><span lang="kn">ಶ್ರೀ ಹರಿ</span> Sri Hari</h3>
      <p>Sri Hari’s posts arrive in the dark, usually between four and five in the morning. Each takes one mantra and does three things: gives it as it is recited, gives the meaning of each word, and then gives the sense of the whole, following Sāyaṇa’s great commentary. He works through a hymn a verse at a time, and so far has taken his readers through the Puruṣa Sūkta, the Śrī Sūkta, the riddling Asya Vāmīya, the wedding hymn of Sūryā and more.</p>
      <p>He is careful to say he is a student, not a scholar. His readers disagree. “Sāyaṇa shines in Hari,” one of them wrote.</p>
      <p class="facts"><span><b>{n['mantra']}</b> mantras</span><span><b>{len([s for s in series if any(e.get('series') == s['key'] for e in by_type('mantra'))])}</b> hymns</span><span>since <b>November 2025</b></span></p>
      <p><a href="mantras.html">Read the mantras →</a></p>
    </div>
  </article>
  <article class="person" id="kusha">
    {portrait("kusha", "", "lg")}
    <div class="person-body">
      <p class="eyebrow">{bi("ಮೂಢ ಮನುಜ", "Mūḍha Manuja")} · on handmade paper</p>
      <h3><span lang="kn">ಕುಶ ಎನ್ ಎಂ</span> Kusha N M</h3>
      <p>Kusha writes a four-line verse each morning, around sunrise, and every one ends by turning to the reader: <i lang="kn">ಮೂಢಮನುಜ</i>, “O deluded one”. The form echoes D. V. Gundappa’s <i>Maṅkutimmana Kagga</i>, with its shared second consonant across all four lines (<i>ādiprāsa</i>). The subjects are anger, money, time, pride and patience: the ordinary places where a life goes wrong or right.</p>
      <p>The rebuke is gentle, and it is meant for everyone, the poet included.</p>
      <p class="facts"><span><b>{n['poem']}</b> verses</span><span>since <b>18 November 2025</b></span></p>
      <p><a href="verses.html">Read the verses →</a></p>
    </div>
  </article>
  <article class="person" id="manjunatha">
    {portrait("manjunatha", "", "lg")}
    <div class="person-body">
      <p class="eyebrow">{bi("ಧರ್ಮಸೂಕ್ಷ್ಮ", "Dharma Sūkṣma")} · on copper plate</p>
      <h3><span lang="kn">ಮಂಜುನಾಥ ಶಾಸ್ತ್ರಿ</span> Manjunatha Shastri</h3>
      <p>Manjunatha Shastri began the circle in December 2023, and he keeps it practical. When someone asks why the bell is rung at a certain point in the Rudrābhiṣeka, he recalls putting the same question to the Śṛṅgeri pontiff years ago, and the answer he got: there is no śāstric reason. When the timing of a ritual is in doubt, he works out the Abhijit muhūrta to the minute.</p>
      <p>It was also his suggestion, in November 2025, that each mantra post should name its seer, its deity and its metre. Within a week Sri Hari’s posts did.</p>
      <p class="facts"><span><b>{n['dharma']}</b> plates so far</span><span>shared <b>as questions arise</b></span></p>
      <p><a href="dharma.html">Read the Dharma Sūkṣma →</a></p>
    </div>
  </article>
</section>

<section class="numbers">
  <h2 class="sec-h">{bi("ಅಂಕಿ ಅಂಶಗಳು", "By the numbers")}</h2>
  {stats}
  <div class="viz-row">{f1}{f2}</div>
</section>

<section class="mv-wrap">{more_voices("", True)}</section>

<section class="materials">
  <h2 class="sec-h">{bi("ಮೂರು ಮಾಧ್ಯಮಗಳು", "Three materials")}</h2>
  <div class="mat-row">
    <div class="mat"><span class="mat-swatch s-palm"></span><h3>Palm leaf</h3><p>For centuries the Veda was carried in memory and copied onto dried palm leaves, strung together through two holes. Sri Hari’s mantras are set on leaves.</p></div>
    <div class="mat"><span class="mat-swatch s-paper"></span><h3>Handmade paper</h3><p>A poet’s notebook: rag paper with a rough edge and indigo ink. Kusha’s verses are set on paper.</p></div>
    <div class="mat"><span class="mat-swatch s-copper"></span><h3>Copper plate</h3><p>Grants and rulings of dharma were engraved on copper plates and bound with a sealed ring. Manjunatha Shastri’s notes are set on copper.</p></div>
  </div>
</section>

<section class="prose-sec">
  <h2 class="sec-h">{bi("ಇಂಗ್ಲಿಷ್ ಅನುವಾದ", "About the English")}</h2>
  <div class="prose">
    <p>The English is drafted with AI assistance from the Kannada, then read by {esc(SITE['editor'])}. It tries to be faithful first and readable second. For the mantras it follows the authors’ own word-by-word glosses; for the verses it keeps the four-line shape and adds a short note where a pun or a play on words cannot cross into English. Romanized text is generated automatically. The Kannada is always the original.</p>
    <p>If you spot a mistake, or would like your own daily practice to appear here, write to {esc(SITE['editor'])} at <a class="email" href="mailto:{SITE['editor_email']}">{SITE['editor_email']}</a>.</p>
  </div>
</section>

<section class="prose-sec">
  <h2 class="sec-h">{bi("ಮೂಲ", "Where it began")}</h2>
  <div class="prose">
    <p>All three write for <span lang="kn">ವೈದಿಕ ಮಿತ್ರರು</span> (Vaidika Mitraru, “friends of the Veda”), a WhatsApp circle of Vedic scholars, practitioners and seekers that Manjunatha Shastri started in December 2023. Most of what passes through it is the ordinary business of friends: invitations, festival greetings, arrangements for the next homa. This site keeps the part that is meant to last. New posts are added every morning at 8.</p>
  </div>
</section>"""

if __name__ == "__main__":
    build()
