"""Source A+B: guess the company's website from its name, then look for a VAT
number on the homepage and its legal pages (terms, privacy, contact, about).

Identity rule (from the manual pilot): a website only counts as the company's
if its Companies House number appears on it. Name similarity is NOT enough.

Usage:
    python -m src.sources.website --limit 50          # first 50 by process_order
    python -m src.sources.website --start 51 --limit 50
Results are appended to results/website.csv, so runs can be resumed.
"""
import argparse
import csv
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from src.vat import normalise, checksum_ok

SAMPLE = "data/sample/sample.csv"
OUT = "results/website.csv"
UA = "Mozilla/5.0 (research project; UK VAT discovery feasibility study)"
TIMEOUT = 8
MAX_PAGES = 6          # homepage + up to 5 legal pages per site
LEGAL_WORDS = ("terms", "condition", "privacy", "legal", "contact", "about",
               "imprint", "policy", "delivery", "returns")
SUFFIXES = r"\b(limited|ltd|plc|llp|l\.l\.p|uk|u\.k|the|company|co)\b"

FIELDS = ["process_order", "stratum", "CompanyNumber", "CompanyName",
          "domain", "status", "ch_found", "vat_candidates", "vat_labelled",
          "evidence_url", "pages_fetched", "seconds"]


# ---------- 1. company name -> candidate domains ----------
def guess_domains(name: str) -> list[str]:
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[.'’]", "", s)
    s = re.sub(SUFFIXES, " ", s)
    words = re.findall(r"[a-z0-9]+", s)
    if not words:
        return []
    slugs = ["".join(words)]
    if len(words) > 1:
        slugs.append("-".join(words))
    out = []
    for slug in slugs:
        for tld in (".co.uk", ".com", ".uk"):
            out.append(slug + tld)
    return out


# ---------- 2. fetching ----------
def fetch(url: str, session: requests.Session) -> tuple[str, str] | None:
    """Return (final_url, html) or None."""
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and "html" in r.headers.get("content-type", ""):
            return r.url, r.text
    except requests.RequestException:
        pass
    return None


def find_site(domains: list[str], session) -> tuple[str, str, str] | None:
    for d in domains:
        for url in (f"https://www.{d}", f"https://{d}"):
            got = fetch(url, session)
            if got:
                return d, got[0], got[1]
    return None


def legal_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    host = urlparse(base_url).netloc
    links = []
    for a in soup.find_all("a", href=True):
        text = (a.get_text(" ") + " " + a["href"]).lower()
        if any(w in text for w in LEGAL_WORDS):
            url = urljoin(base_url, a["href"]).split("#")[0]
            if urlparse(url).netloc == host and url not in links:
                links.append(url)
    return links[: MAX_PAGES - 1]


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" "))


# ---------- 3. extraction ----------
VAT_RE = re.compile(
    r"(?<![\dA-Za-z])((?:GB|XI)?\s?\d{3}\s?\d{4}\s?\d{2}(?:\s?GB)?)(?![\d])")
VAT_LABEL = re.compile(r"\bVAT\b|V\.A\.T", re.I)


def extract_vat(text: str) -> list[tuple[str, bool]]:
    """Return [(9-digit number, labelled)] that pass the checksum.

    labelled = the word 'VAT' appears within 60 chars before the number.
    Unlabelled numbers are kept only if written with a GB/XI prefix or suffix
    (a bare 9-digit number with no label is too likely to be something else).
    """
    found = {}
    for m in VAT_RE.finditer(text):
        raw = m.group(1)
        digits = normalise(raw)
        if not digits or not checksum_ok(digits):
            continue
        labelled = bool(VAT_LABEL.search(text[max(0, m.start() - 60): m.start()]))
        prefixed = bool(re.search(r"GB|XI", raw))
        if labelled or prefixed:
            found[digits] = found.get(digits, False) or labelled
    return list(found.items())


def ch_number_on_page(text: str, crn: str) -> bool:
    """CH numbers are often printed without leading zeros (01081551 -> 1081551)."""
    m = re.match(r"([A-Z]{2})?(\d+)", crn.strip().upper())
    if not m:
        return False
    prefix, num = m.group(1) or "", m.group(2).lstrip("0")
    pattern = rf"(?<![\dA-Z]){prefix}\s?0*{num}(?!\d)"
    return re.search(pattern, text, re.I) is not None


# ---------- 4. one company ----------
def process(row: dict) -> dict:
    t0 = time.time()
    res = {k: row.get(k, "") for k in FIELDS}
    res.update(domain="", ch_found=False, vat_candidates="", vat_labelled="",
               evidence_url="", pages_fetched=0)
    s = requests.Session()
    s.headers["User-Agent"] = UA

    site = find_site(guess_domains(row["CompanyName"]), s)
    if not site:
        res["status"] = "no_site"
    else:
        domain, home_url, home_html = site
        res["domain"] = domain
        pages = [(home_url, home_html)]
        for url in legal_links(home_html, home_url):
            got = fetch(url, s)
            if got:
                pages.append(got)
        res["pages_fetched"] = len(pages)

        vats = {}
        for url, html in pages:
            text = page_text(html)
            if ch_number_on_page(text, row["CompanyNumber"]):
                res["ch_found"] = True
            for num, lab in extract_vat(text):
                if num not in vats:
                    vats[num] = (lab, url)
        res["vat_candidates"] = ";".join(vats)
        res["vat_labelled"] = ";".join(str(v[0]) for v in vats.values())
        res["evidence_url"] = ";".join(v[1] for v in vats.values())

        if not res["ch_found"]:
            res["status"] = "site_unconfirmed"     # can't trust anything here
        elif vats:
            res["status"] = "confirmed_vat_found"
        else:
            res["status"] = "confirmed_no_vat"
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ---------- 5. batch runner ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    with open(SAMPLE, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f)
                if args.start <= int(r["process_order"]) < args.start + args.limit]

    done = set()
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            done = {r["CompanyNumber"] for r in csv.DictReader(f)}
    rows = [r for r in rows if r["CompanyNumber"] not in done]
    print(f"Processing {len(rows)} companies (skipping {len(done)} already done)")

    new_file = not os.path.exists(OUT)
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        with ThreadPoolExecutor(args.workers) as pool:
            futures = [pool.submit(process, r) for r in rows]
            for i, fut in enumerate(as_completed(futures), 1):
                res = fut.result()
                w.writerow(res)
                f.flush()
                print(f"[{i}/{len(rows)}] {res['status']:<20} {res['CompanyName'][:40]:<40} {res['domain']}")


if __name__ == "__main__":
    main()