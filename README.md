# svadhyaya
svādhyāyān mā pramadaḥ
“Never neglect your daily study.” — Taittirīya Upaniṣad 1.11

## The site

Daily Veda mantra meanings (Sri Hari), *Mūḍha Manuja* verses (Kusha N M) and *Dharma Sūkṣma* notes (Manjunatha Sharma), in Kannada with English alongside.

- `content/entries/*.json`: one file per post (Kannada original + English `en` block)
- `content/series.json`: sūkta series (date ranges, names, verse counts)
- `scripts/extract.py <chat.txt>`: pulls new posts from a WhatsApp export (rules in `scripts/rules.json`)
- `scripts/set_en.py <translations.json>`: merges English translations
- `build.py`: builds the static site into `public/`

Cloudflare Pages: build command `pip install -r requirements.txt && python3 build.py`, output directory `public`.
The raw chat export is never committed.
