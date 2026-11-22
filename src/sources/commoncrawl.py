"""Source C: Common Crawl, inverted.

Instead of company -> website -> VAT, scan a random slice of one monthly crawl
once and extract every page where a Companies House number and a VAT number
appear together. Then join those pairs to the CH register.

Usage:
    python -m src.sources.commoncrawl --files 2            # quick test
    python -m src.sources.commoncrawl --files 20           # main run
Files already processed are skipped, so the run can be resumed.

Outputs:
    results/cc_pairs.csv   one row per (page, CH number, VAT number)
    results/cc_stats.csv   one row per WET file: pages, pages mentioning VAT, ...
"""
import argparse
import csv
import gzip
import io
import os
import random
import re
import time

import requests
from warcio.archiveiterator import ArchiveIterator

from src.sources.website import extract_vat

BASE = "https://data.commoncrawl.org/"
SEED = "veridion-2026-11-22"
PAIRS = "results/cc_pairs.csv"
STATS = "results/cc_stats.csv"
UA = {"User-Agent": "UK VAT discovery feasibility study (research)"}

PAIR_FIELDS = ["wet_file", "url", "host", "ch_number", "vat", "vat_labelled",
               "n_ch_on_page", "n_vat_on_page"]
STAT_FIELDS = ["wet_file", "pages", "pages_with_vat_word", "pages_with_vat",
               "pages_with_ch", "pages_with_pair", "pairs", "seconds"]

# CH number = 8 chars: digits, or 2-letter prefix (SC, NI, OC, SO, NC, ...) +
# 6 digits. Often printed without leading zeros. We require a label before it
# ("company no", "registered number", "registration no" ...) to avoid
# picking up random 6-8 digit numbers.
CH_RE = re.compile(
    r"(?:company|registered|registration|reg\.?)\s*"
    r"(?:in\s+(?:england|scotland|wales|northern ireland)(?:\s+and\s+wales)?"
    r"\s*(?:&\s*wales)?\s*)?"
    r"(?:no\.?|number|num\.?|#)?\s*[:.\-]?\s*"
    r"((?:SC|NI|OC|SO|NC|SL|R0)?\s?\d{5,8})(?!\d)",
    re.I)


def norm_ch(raw: str) -> str:
    s = raw.upper().replace(" ", "")
    m = re.match(r"([A-Z]{2})?(\d+)$", s)
    prefix, digits = m.group(1) or "", m.group(2)
    return prefix + digits.zfill(8 - len(prefix))


def extract_ch(text: str) -> list[str]:
    return sorted({norm_ch(m.group(1)) for m in CH_RE.finditer(text)})


def latest_crawl() -> str:
    r = requests.get("https://index.commoncrawl.org/collinfo.json",
                     headers=UA, timeout=30)
    return r.json()[0]["id"]


def wet_paths(crawl: str) -> list[str]:
    r = requests.get(f"{BASE}crawl-data/{crawl}/wet.paths.gz",
                     headers=UA, timeout=60)
    return gzip.decompress(r.content).decode().split()


def process_file(path: str, pair_writer) -> dict:
    t0 = time.time()
    st = dict.fromkeys(STAT_FIELDS, 0)
    st["wet_file"] = path
    with requests.get(BASE + path, headers=UA, stream=True, timeout=120) as r:
        r.raise_for_status()
        for rec in ArchiveIterator(r.raw):
            if rec.rec_type != "conversion":
                continue
            st["pages"] += 1
            text = rec.content_stream().read().decode("utf-8", "replace")
            if not re.search(r"\bVAT\b", text, re.I):   # cheap pre-filter
                continue
            st["pages_with_vat_word"] += 1
            vats = extract_vat(text)
            chs = extract_ch(text)
            st["pages_with_vat"] += bool(vats)
            st["pages_with_ch"] += bool(chs)
            if not (vats and chs):
                continue
            st["pages_with_pair"] += 1
            url = rec.rec_headers.get_header("WARC-Target-URI")
            host = re.sub(r"^https?://", "", url).split("/")[0].lower()
            for ch in chs:
                for vat, labelled in vats:
                    pair_writer.writerow(dict(
                        wet_file=path, url=url, host=host, ch_number=ch,
                        vat=vat, vat_labelled=labelled,
                        n_ch_on_page=len(chs), n_vat_on_page=len(vats)))
                    st["pairs"] += 1
    st["seconds"] = round(time.time() - t0, 1)
    return st


def open_append(path, fields):
    new = not os.path.exists(path)
    f = open(path, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(f, fieldnames=fields)
    if new:
        w.writeheader()
    return f, w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", type=int, default=2)
    ap.add_argument("--crawl", default=None, help="e.g. CC-MAIN-2026-43")
    args = ap.parse_args()

    crawl = args.crawl or latest_crawl()
    paths = wet_paths(crawl)
    random.Random(SEED).shuffle(paths)          # random, reproducible slice
    chosen = paths[: args.files]
    print(f"Crawl {crawl}: {len(paths)} WET files, using {len(chosen)}")

    done = set()
    if os.path.exists(STATS):
        with open(STATS, newline="", encoding="utf-8") as f:
            done = {r["wet_file"] for r in csv.DictReader(f)}

    os.makedirs("results", exist_ok=True)
    pf, pw = open_append(PAIRS, PAIR_FIELDS)
    sf, sw = open_append(STATS, STAT_FIELDS)
    for i, path in enumerate(chosen, 1):
        if path in done:
            print(f"[{i}/{len(chosen)}] skip (done)")
            continue
        try:
            st = process_file(path, pw)
        except Exception as e:                   # network hiccup: skip, retry later
            print(f"[{i}/{len(chosen)}] FAILED {e}")
            continue
        sw.writerow(st)
        pf.flush(); sf.flush()
        print(f"[{i}/{len(chosen)}] pages={st['pages']:>6} vat_word={st['pages_with_vat_word']:>5} "
              f"vat={st['pages_with_vat']:>4} ch={st['pages_with_ch']:>4} "
              f"pair_pages={st['pages_with_pair']:>3} ({st['seconds']}s)")
    pf.close(); sf.close()


if __name__ == "__main__":
    main()