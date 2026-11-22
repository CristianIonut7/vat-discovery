"""Analyse the Common Crawl pairs (source C).

Inputs : results/cc_pairs.csv, results/cc_stats.csv, data/raw/ch.parquet,
         data/sample/sample.csv
Outputs: results/cc_companies.csv   one row per CH number (the PoC dataset)
         results/cc_hmrc_check.csv  30 random companies to verify by hand at HMRC
Prints a summary to paste into the log.

Run: python -m src.analyse_cc
"""
import duckdb
import numpy as np
import pandas as pd

SEED = 20261122
W = (8, 7, 6, 5, 4, 3, 2)


def scheme(v: str) -> str:
    t = sum(int(d) * w for d, w in zip(v[:7], W)) + int(v[7:])
    return "old" if t % 97 == 0 else "new"


def main():
    stats = pd.read_csv("results/cc_stats.csv")
    p = (pd.read_csv("results/cc_pairs.csv", dtype=str)
           .drop_duplicates(["wet_file", "url", "ch_number", "vat"]))  # re-run duplicates
    p["n_ch"] = p.n_ch_on_page.astype(int)
    p["n_vat"] = p.n_vat_on_page.astype(int)

    print("=== 1. Corpus yield ===")
    print(f"WET files: {len(stats)}  pages: {stats.pages.sum():,}")
    print(f"pages with a (CH, VAT) pair: {p.url.nunique():,}  unique pairs: {len(p):,}")

    # Keep only unambiguous pages: exactly one CH number and one VAT number.
    s = p[(p.n_ch == 1) & (p.n_vat == 1)].copy()
    print(f"single-company pages: {s.url.nunique():,} "
          f"({s.url.nunique() / p.url.nunique():.1%} of pair pages) → used below")

    print("\n=== 2. Consistency ===")
    vats_per_ch = s.groupby("ch_number").vat.nunique()
    chs_per_vat = s.groupby("vat").ch_number.nunique()
    print(f"unique CH numbers: {len(vats_per_ch):,}")
    print(f"CH numbers seen with >1 VAT number: {(vats_per_ch > 1).sum()}")
    print(f"VAT numbers seen with >1 CH number: {(chs_per_vat > 1).sum()} "
          f"(VAT groups, agencies, or errors)")

    print("\n=== 3. How many companies would the full crawl give? ===")
    files = s.wet_file.unique()
    rng = np.random.default_rng(SEED)
    curve = {}
    for k in (50, 100, 200, 300, 400, len(files)):
        vals = [s[s.wet_file.isin(set(rng.choice(files, k, replace=False)))]
                .ch_number.nunique() for _ in range(20)]
        curve[k] = np.mean(vals)
        print(f"  {k:>4} files → {curve[k]:,.0f} unique companies")
    k0, k1 = 50, len(files)
    b = np.log(curve[k1] / curve[k0]) / np.log(k1 / k0)
    full = curve[k1] * (100_000 / k1) ** b
    cnt = s.groupby("ch_number").wet_file.nunique()
    f1, f2 = (cnt == 1).sum(), (cnt == 2).sum()
    chao1 = len(cnt) + f1 * f1 / (2 * f2)
    print(f"  power-law exponent b = {b:.2f} → full crawl (100k files) ≈ {full:,.0f} "
          f"(likely an OVER-estimate: b falls as the sample grows)")
    print(f"  Chao1 lower bound ≈ {chao1:,.0f} (weak at a 0.5% sample)")

    # One row per company: most frequent VAT number, number of pages, example URL
    comp = (s.groupby(["ch_number", "vat"])
              .agg(n_pages=("url", "nunique"), example_url=("url", "first"),
                   hosts=("host", lambda x: ";".join(sorted(set(x))[:3])))
              .reset_index()
              .sort_values(["ch_number", "n_pages"], ascending=[True, False]))
    comp["n_vat_candidates"] = comp.groupby("ch_number").vat.transform("count")
    comp = comp.drop_duplicates("ch_number")
    comp["vat_scheme"] = comp.vat.map(scheme)

    print("\n=== 4. Join with Companies House ===")
    con = duckdb.connect()
    con.register("comp", comp)
    j = con.sql("""
        SELECT comp.*, ch.CompanyName, ch.CompanyStatus, ch.CompanyCategory,
               ch."Accounts.AccountCategory" AS account_category,
               ch.IncorporationDate,
               ch."RegAddress.PostTown" AS town, ch."RegAddress.PostCode" AS postcode
        FROM comp LEFT JOIN 'data/raw/ch.parquet' ch
          ON comp.ch_number = ch.CompanyNumber
    """).df()
    found = j.CompanyName.notna()
    print(f"CH number exists in the live register snapshot: {found.sum():,} / {len(j):,} "
          f"({found.mean():.1%})  (missing = dissolved, typo, or non-company number)")
    print(j.loc[found, "CompanyStatus"].value_counts().head(5).to_string())
    print(j.loc[found, "account_category"].value_counts().head(8).to_string())

    yr = pd.to_numeric(j.IncorporationDate.str[-4:], errors="coerce")
    young_old = (yr >= 2011) & (j.vat_scheme == "old")
    print(f"\nincorporated 2011+ but old-scheme VAT number: {young_old.sum()} "
          f"of {(yr >= 2011).sum()} → likely group/other-entity numbers or errors")
    j["flag_scheme"] = young_old
    j.to_csv("results/cc_companies.csv", index=False)

    print("\n=== 5. Overlap with my 500-company sample ===")
    smp = pd.read_csv("data/sample/sample.csv", dtype=str)
    hit = smp.merge(comp, left_on="CompanyNumber", right_on="ch_number")
    print(f"sample companies found in the 0.5% crawl slice: {len(hit)} / {len(smp)}")
    if len(hit):
        print(hit.groupby("stratum").size().to_string())
        print(hit[["process_order", "stratum", "CompanyName", "vat", "example_url"]]
              .to_string(index=False))

    # 30 random companies (that exist in CH) for the manual HMRC precision check
    chk = (j[found].sample(n=min(30, found.sum()), random_state=SEED)
             [["ch_number", "CompanyName", "town", "postcode", "vat",
               "vat_scheme", "flag_scheme", "example_url"]])
    for col in ("hmrc_valid", "hmrc_name", "hmrc_postcode", "match"):
        chk[col] = ""
    chk.to_csv("results/cc_hmrc_check.csv", index=False)
    print("\nwrote results/cc_companies.csv and results/cc_hmrc_check.csv (30 rows)")


if __name__ == "__main__":
    main()