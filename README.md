# Can a UK company VAT dataset be built from the open web?

Evidence: every claim points to where it came from. "(log 16:58)" refers to
the timestamped entry in [notes/log.md](notes/log.md); details are in
[notes/pilot.md](notes/pilot.md) and [notes/aggregators.md](notes/aggregators.md).

*Short on time:* read the TL;DR, the sources table (2.2), the results (3.3)
and what breaks first (4.4).

## TL;DR

**Partly.** From the open web you can build a precise UK VAT dataset for a
minority of companies, mostly established and larger ones, but not full
coverage: new and micro companies are almost invisible, and roughly a third or
more of target companies are probably not VAT-registered at all.

- **What works:** scanning Common Crawl for pages that carry both a company's CH
  number and a VAT number. 0.5% of one monthly crawl (10.6M pages, 44 minutes
  on a laptop) gave 5,986 companies; of 33 numbers checked at HMRC, none was
  wrong and unflagged (95% upper bound ≈ 10%). The full crawl would give tens of
  thousands to a few hundred thousand companies, at well under $0.001 each.
- **Where it breaks:** coverage is strongly skewed: large companies are ~8x
  more likely to be found than micro companies and ~80x more than new ones.
  VAT groups mean the right number is often registered to another company,
  and only ownership data can tell a group from an error.
- **Dead ends:** guessing websites from company names (0 of 2), aggregators as a
  source (unlicensable, partial, sometimes wrong), LLM answers.
- **The benchmark:** name→VAT lookups are already sold (vat-search, ~0.045 EUR
  each), apparently built by enumerating HMRC's checker. The customer could
  fill its 26.7k gaps for ~1.2-1.6k EUR. A product has to beat that.

## 1. Problem framing

The customer has 40,000 UK suppliers and a VAT number for about a third of them.
They use the VAT number to match each incoming invoice to the right supplier, so
what they need is **the number printed on each supplier's invoices**.

That is not always a number registered in the supplier's own name. Companies in a
VAT group share one number, registered to the parent. Argos Limited, for example,
shows VAT number 660 4548 36 on its website, and HMRC returns the name
"Sainsbury's Supermarkets Ltd" for it, because Argos belongs to the Sainsbury's
group. For invoice matching this number is correct. But a simple safety rule such
as "accept a number only if the HMRC name equals the Companies House name" would
reject it.

Four constraints shaped everything that follows:

1. **Verification only runs backwards.** HMRC confirms a number and returns the
   registered name and address, but never gives a number for a company. Every
   approach is "find a candidate somewhere, then verify it".
2. **A wrong number costs more than a missing one.** A valid number attached to
   the wrong company silently breaks every downstream join. I optimise for
   precision first and need an explicit rule for "this number belongs to this
   company".
3. **"Not found" is ambiguous.** There are ~2.18M VAT registrations in the UK,
   including sole traders, against ~3.58M companies in my target population
   (section 3.1). Many companies are simply not registered, so coverage can
   never approach 100%.
4. **There is no ground truth.** The only check is HMRC itself, so precision has
   to be measured by verifying a random sample by hand.

So the question is not "can I scrape some VAT numbers", but: which sources
exist, which of them work for which kinds of companies, how often they are
wrong, and what it would cost to do this properly.

## 2. Part 1 - Research trail

### 2.1 Where I started

Before writing any code I wrote down four hypotheses (log 16:58):

| # | Hypothesis | Outcome |
|---|---|---|
| H1 | GB VAT numbers carry a mod-97 checksum, so random 9-digit numbers on a page can be filtered out | **Confirmed.** All real numbers pass; the filter is what makes extraction from web pages usable. But checksum-valid doesn't mean registered: 3 numbers passed and were unknown to HMRC. |
| H2 | The VAT number cannot be derived from the Companies House number | **Consistent with everything I saw.** The UK is a pure discovery problem (unlike France, section 6). |
| H3 | A company's EORI number contains its VAT number | **Supported** by vat-search's API docs (GB + VAT + 000), not tested. It does not help discovery: the EORI checker also only verifies. |
| H4 | Companies selling online show their VAT number on their website | **True for a minority:** 2 of 10 in my manual pilot. In Common Crawl, 79% of pages with a VAT number also show the company's CH number. |

### 2.2 Sources I looked at

| Source | What I did | Result | Verdict |
|---|---|---|---|
| **HMRC API** (production) | Requested production access (log 17:04) | Compliance questionnaire, a named "responsible individual", manual review | Not available to an individual in a weekend; a prerequisite at scale |
| **HMRC web checker** | Used for every number I report (40+ checks) | Validity, registered name and address; no captcha seen | **Used.** The ground truth here |
| **Company websites, by hand** | Manual pilot, first 10 sample companies, ~25 min (log 21:25) | Website 6/10, confirmed by CH number 3/10; correct VAT on own site 2/10 | Works once you know the website; doesn't scale |
| **A+B: guess the domain from the name** | `src/sources/website.py` on the same 10 (log 21:51) | 0 of the 2 numbers found by hand on own sites | **Dead end** (2.3) |
| **C: Common Crawl, inverted** | 500 random WET files = 0.5% of one monthly crawl (log 23:15) | 5,986 companies; 0 of 31 valid numbers belonged to an unrelated company | **Works.** Precise, nearly free, skewed to large companies |
| **D: aggregators** (vat-search, vat-lookup, Endole) | Terms, pricing, lookups on companies with known numbers ([notes](notes/aggregators.md)) | Correct when they had a number, but coverage 0/3 and 1/3, one wrong VAT = CH link, no resale rights | Signal or licensing partner, not a source |
| **LLM answers** (Gemini) | Appeared during manual search (log 21:25) | Right once, offered other companies' numbers once | **Not a source** |
| **eBay business sellers** | Seen while collecting test numbers (log 17:20) | One valid, one unknown to HMRC | Not tested at scale; eBay sellers only |

Two things became clear. "Find the VAT number" is really three problems:
getting from the company to its website (hard), finding the number on it (easy
when it is there), and aggregators outside both. And every source that works
needs a way to prove that a number belongs to a specific company (2.4).

### 2.3 Dead ends

**Guessing the website from the company name (A+B).** I expected most
companies to have a site named after them, so `src/sources/website.py` tries
variants (`thunderenergyservices.co.uk`, `.com`, `thunder-energy-services.co.uk`
...), fetches the homepage and legal pages, and accepts a VAT number only if the
company's CH number is on the same site. On the 10 pilot companies it recovered
**0 of the 2** numbers I had found by hand (log 21:51):

| Company | Real domain | Why guessing fails |
|---|---|---|
| British Arab Commercial Bank PLC | bacb.co.uk | acronym |
| Clearwater Servicing Ltd | clearwaterltd.com | brand differs legal name |
| Thunder Energy Services Ltd | thunderenergy.co.uk | generic word dropped |

The script could download thunderenergy.co.uk, so the failure is the guessing,
not blocking. The two sites it did find by name were correctly refused: neither
shows the CH number. My HMRC sample repeats the pattern: The Ardent Partnership
trades as sayitwithsongs.com, Castello Interiors as vanfitsolutions.co.uk.
Getting from a company to its website needs a search engine, or a corpus where
the CH number leads to the page.

**Aggregators as a product source** ([notes/aggregators.md](notes/aggregators.md)).
On three companies whose numbers I know exist, vat-lookup found 0 by name and
Endole showed 1; vat-search cannot be searched without an account. vat-lookup
ties Chubb Services UK's number to a closed company with another CH number
(01112892 vs 01509033), exactly the invisible error the customer fears. None of
the three allows resale or scraping, and none warrants accuracy.

**HMRC's production API** needs organisational onboarding (log 17:04), so I
verified by hand on the web checker. **LLM answers**: for Blue Jay of London,
Gemini offered the numbers of two differently named companies; I count only
numbers I can trace to a page.

### 2.4 What I learned that wasn't obvious

**1. VAT groups break the obvious match rule.** Besides Argos (section 1),
Go Outdoors publishes JD Sports' number (log 17:34), and 2 of 31 valid numbers
from Common Crawl were registered to another group company (log 23:45). A name
mismatch is a flag, not proof of an error.

**2. The CH number on the same page is the best identity anchor.** UK
companies must show their registered number on their websites (Company, LLP
and Business (Names and Trading Disclosures) Regulations 2015, reg. 25); 79% of
Common Crawl pages with a VAT number carry one. It avoids fuzzy name matching,
but only if applied exactly: in the pilot I "confirmed" a Clearwater site by eye,
yet its footer reads 09476227, not Clearwater Servicing's 05048291. It is a
sister company of Wilton Bradley Ltd selling under the brand "Clearwater®", and
HMRC registers the number to Wilton Bradley (log 2026-11-23 21:15). A script
comparing digits would have rejected it.

**3. Names and addresses are poor match keys.** The HMRC postcode equals the
Companies House postcode for only **15 of 31** valid numbers (log 23:45): the
registered office is often an accountant. Registered names change too:
Chubb's number had five names since 2019, including one month as "Courtiers
Group Holdings Limited" (log 23:00).

**4. The checksum scheme hints at when a number was issued.** GB numbers use
two schemes (total divisible by 97, or total + 55 divisible by 97). All 8 real
numbers I held are consistent with the newer one starting around November 2009:

    def scheme(v: str) -> str:            # src/analyse_cc.py
        t = sum(int(d) * w for d, w in zip(v[:7], (8, 7, 6, 5, 4, 3, 2))) + int(v[7:])
        return "old" if t % 97 == 0 else "new"

A company incorporated after 2010 with an old-scheme number is probably using
another entity's number: 170 of 2,947 in Common Crawl (5.8%). A reason to check,
not to reject: Kellockbank Ltd has one, registered in its own name.

**5. Someone has very likely enumerated HMRC's checker already.** The checksum
allows about **20.6 million** valid GB numbers. vat-search claims **21 million
UK VAT IDs**, against ~2.18M active registrations, and HMRC publishes no list.
The most plausible explanation is systematic querying (an inference; log 22:49).

## 3. Part 2 - Proof of concept

### 3.1 The sample

**Source:** Companies House bulk snapshot of 1 Nov 2026: 5,711,779 companies,
5,179,256 active (log 17:48).

**Target population.** I excluded only what cannot be a supplier, never what is
merely hard to find (log 18:15): active Private Limited companies, PLCs and LLPs;
out go dormant companies and companies whose *every* SIC code is real estate,
holding company, residents' management or dormant (68100 + 47910 still trades):

    -- src/sample.py
    acc = 'DORMANT'
    OR (len(sics) > 0 AND len(list_filter(sics,
          lambda x: NOT (x LIKE '68%' OR x IN ('64209', '98000', '99999')))) = 0)

Companies incorporated in 2025-26 are **kept on purpose**: they have not filed
accounts yet (log 17:57), and leaving them out would remove the hardest cases.

| Stratum | Accounts category | Population | Share |
|---|---|---|---|
| micro | MICRO ENTITY | 1,384,125 | 38.7% |
| new | NO ACCOUNTS FILED, incorporated 2025-26 | 959,573 | 26.8% |
| small_exempt | TOTAL EXEMPTION FULL | 956,898 | 26.7% |
| small | SMALL, UNAUDITED/AUDITED ABRIDGED, TOTAL EXEMPTION SMALL | 173,214 | 4.8% |
| large | FULL, MEDIUM, GROUP, AUDIT EXEMPTION SUBSIDIARY | 107,347 | 3.0% |

**Equal allocation, not proportional** (log 18:20-18:32): proportional would give
~15 large companies, too few to say anything about the stratum that matters most
to a manufacturer. I drew **94 per stratum + 30 from the excluded companies as a
control = 500**, with a fixed seed, in shuffled order (any prefix is still a
random sample). Population-level figures are reweighted by true stratum sizes.

The sample was drawn before looking at any website, so it is not "companies I
knew publish their VAT number". **Was the exclusion right?** Dormant companies
are 0.5% of the companies publishing a VAT number in Common Crawl, against ~11%
of the register (log 00:03). The SIC exclusion was not tested.

### 3.2 The pipeline

    Common Crawl WET files ---> pages mentioning "VAT"
        ---> VAT candidates (regex + mod-97 checksum + label or GB prefix)
        ---> CH number on the same page (labelled only)
        ---> pages with exactly one CH number and one VAT number
        ---> join to Companies House ---> verify a random subsample at HMRC

Two decisions carry the precision. **A CH number counts only with a label**
("Company No.", "Registered in England No.", etc.), otherwise any 6-8 digit number
could pass as one:

    # src/sources/commoncrawl.py
    CH_RE = re.compile(
        r"(?:company|registered|registration|reg\.?)\s*"
        r"(?:in\s+(?:england|scotland|wales|northern ireland)(?:\s+and\s+wales)?\s*)?"
        r"(?:no\.?|number|num\.?|#)?\s*[:.\-]?\s*"
        r"((?:SC|NI|OC|SO|NC|SL|R0)?\s?\d{5,8})(?!\d)", re.I)

And **only unambiguous pages are used**: one CH number and one VAT number.
Directory pages (4% of pair pages) are kept in the raw output, then dropped.
The CH match is exact, digit by digit (unlike my pilot check by eye, 2.4).

### 3.3 Results

**Main result: open-web discovery works for established, larger companies and
barely at all for new ones.** Share of each stratum found in a 0.5% slice of one
monthly crawl (log 23:21):

| Stratum | Found | Population | Share found |
|---|---|---|---|
| large | ~900 | 107,347 | **0.84%** |
| small | ~545 | 173,214 | 0.31% |
| small_exempt | 2,704 | 956,898 | 0.28% |
| micro | 1,453 | 1,384,125 | 0.10% |
| new | 101 | 959,573 | **0.01%** |

A large company is ~8x more likely to be found than a micro one, ~80x more than
a new one.

**Corpus yield** (log 23:15):

| | |
|---|---|
| WET files / pages scanned | 500 / 10,580,125 |
| pages mentioning "VAT" / with a valid VAT number | 117,220 / 19,771 |
| pages with a (CH, VAT) pair | 15,608 (79% of VAT pages), 96% single-company |
| unique companies / CH number exists in the register | 5,986 / 5,834 (97.5%) |
| conflicts: same CH >1 VAT / same VAT >1 CH | 6 / 39 |
| runtime on my laptop | 44 min (~5 s per file) |

**My 500-company sample:** 3 appear in the slice (2 large, 1 small_exempt),
about what 0.5% should give. Derbyshire Aggregates Ltd publishes its number on
resinbondedaggregates.com, a brand domain no name-guessing would find.
**Manual pilot** (first 10): 4 correct numbers after HMRC (2 own sites,
2 aggregators only), 1 wrong candidate (Clearwater, 2.4).

**The full crawl.** Unique companies grow sub-linearly (50 files --> ~1.1k,
500 --> ~6.0k). A power law S(k) = a·kᵇ fitted on 50-500 files gives b = 0.73 and
**~290k** companies for 100k files, an over-estimate as b keeps falling; Chao1
(S + f₁²/2f₂) gives **at least ~12k**, weak at a 0.5% sample. So one crawl holds
tens of thousands to a few hundred thousand companies, against 3.58M.

### 3.4 Precision: measured, not assumed

**30 random companies** from the output plus the **3 sample hits**, checked by hand
at HMRC (results/cc_hmrc_check.csv, log 23:45):

| Outcome | Count |
|---|---|
| valid, HMRC name = Companies House name | 29 |
| valid, registered to another company of the same group | 2 |
| unknown to HMRC (deregistered or wrong on the page) | 2 |
| valid, but belonging to an unrelated company | **0** |

Before verification, 4 of 33 (~12%) are not the company's own valid number.
After HMRC and a name check, invalid numbers drop out and group numbers are
flagged: **0 of 31 valid numbers wrong and unflagged**, i.e. below ~10% at 95%
(rule of three, 3/31).

I did not solve VAT groups automatically: a name mismatch is flagged, not
rejected, and telling a group from an error needs ownership (PSC) data (4.2).

### 3.5 What these numbers don't capture

- **The 500-company sample was only partly used.** Searching every company by
  hand takes ~2.5 minutes, so I did it for the first 10 only; all 500 were
  matched against the Common Crawl slice (3 found, ~1.5 expected from the
  per-stratum rates). The 30-company control group was never searched; the
  exclusion check in 3.1 uses the Common Crawl finds instead. Coverage per
  stratum (3.3) is therefore measured on the whole slice, not on the sample.
- 0.5% of **one** monthly crawl; the full-crawl figure is a wide extrapolation.
- Precision on **33 checks**, by one person.
- The pilot's identity check was by eye and failed once.
- Companies that never publish their number are invisible to this method.
- "Not found" cannot be split into "not registered" and "not published".
- The SIC exclusion was not tested; group links were judged by hand.

## 4. Part 3 - With real resources

Where a number is an estimate, it says so.

### 4.1 Two different jobs

- **The customer** needs ~26.7k missing numbers, mostly for established trading
  companies, where the open web works best. Benchmark: vat-search lookups at
  ~0.045-0.95 EUR each, ~1.2-1.6k EUR in total.
- **A product** means 3.58M companies, kept current and resellable. Much harder.

### 4.2 The pipeline I would build

1. **Common Crawl, all of it.** ~5 s per WET file on my laptop; one crawl
   (100k files) ~= 140 CPU-hours, ~1.5 h on 100 cores next to the Common Crawl
   bucket, a few dollars of compute (order of magnitude). Run every new crawl plus
   the last 12, deduplicated by CH number. Under $0.001 per company found.
2. **Re-crawl known domains** found in step 1, for fresher numbers.
3. **Company --> website with a search API** for the rest. List prices (checked
   Nov 2026): ~$1 per 1,000 queries for Google resellers (with Google's
   terms-of-service risk) to $5 for Brave's own index; Google's Custom Search API
   closes on 1 Jan 2027 and Bing's APIs are retired. At ~2 queries per company:
   **~$50-270** for the customer's 26.7k gaps, **~$7k-36k** for all 3.58M, much of
   it wasted on companies without websites. So: per customer list, or per stratum
   (large → small → small_exempt). Same exact CH-number rule.
4. **HMRC's API** for verification at entry and on a schedule, after checking
   that its terms allow bulk, commercial use.
5. **Group resolution** with the free Companies House PSC (ownership) bulk data:
   if the HMRC-registered entity and the company share a controlling parent or
   person, mark a group number; otherwise reject. The rest goes to an
   **annotation team**: ~6% of numbers were name mismatches in my sample, so on
   ~100k companies ~6k cases, ~100 person-hours if most are resolved
   automatically (estimate).
6. **Optionally license** vat-search's data for companies with no web presence.
   At list price 3.58M lookups ~= 160k EUR, so it is a negotiation; licensed links
   still need the same identity checks.

| Route | Cost per company (estimate) | Coverage | Precision |
|---|---|---|---|
| Common Crawl, inverted | < $0.001 | low, skewed to large | high |
| Re-crawl of known domains | ~$0.001 | same companies, fresher | high |
| Search API + crawl | ~$0.002-0.01 per company searched | medium for large/small | high with the CH rule |
| Manual review | ~2 min ~= £0.5-1 per case (£15-30/h) | — | resolves hard cases |
| Licensed aggregator | 0.045-0.95 EUR per lookup | high claimed, unmeasured | links need checking |

### 4.3 How coverage and accuracy would change

Large and small companies should be well covered once all crawls and search are
used; this is most of what the customer needs. Micro companies stay low and new
companies stay almost invisible whatever the budget: they need other sources
(the customer's onboarding data, invoices, a licence). Precision stays high as
long as the CH match is exact and groups are resolved with ownership data.

### 4.4 What breaks first

1. **HMRC's terms for bulk verification.** If commercial bulk verification or
   re-verification is not allowed, there is no other source of truth.
2. **Group resolution.** Name mismatches can be groups (THG, Clearway) or
   errors (Clearwater); PSC data has gaps (overseas parents, individuals
   controlling several companies), so the manual queue grows with coverage.
3. **New and micro companies.** Coverage there does not scale with money.
4. **Staleness.** vat-lookup's Chubb record changed name and address several
   times in five years and was two years stale when I looked.

### 4.5 What I would monitor

- Invalid rate at re-verification, per source and month.
- Name-mismatch rate, and how many PSC resolves vs people.
- Conflict rate (same CH with >1 VAT; same VAT on unrelated CH numbers).
- Scheme-vs-age flag rate (5.8% in my slice).
- Coverage per stratum vs the previous run, so a broken extractor shows up as a
  drop in one stratum.
- A monthly random audit checked by a person: 0 errors in 100 bounds the rate at ~3%.

## 5. Debate topics

**Pointing the checksum at HMRC's checker.** Possible (~20.6M valid numbers,
~24 days at 10 requests/second) and very likely done (vat-search's 21M). I would
not build on it: it gives every number with a name, but **not which company it
belongs to**, and matching back by name and address is exactly what my data shows
to be unreliable (2.4); much of it is **sole traders' personal data** (GDPR); and
it uses a public service in a way it was not designed for, which has to be
checked against HMRC's terms and is a reputational risk even if allowed. Better
to license it from whoever holds it, and still check the links.

**Keeping it current.** Re-verify every number at HMRC on a schedule, more often
where risk is higher (new companies, mismatches, old-scheme numbers on young
companies), storing and diffing each result as vat-lookup does. React to
Companies House events (incorporations, dissolutions, name and PSC changes).
Re-run every monthly crawl. Track the age of each record's last verification.

**Knowing it's wrong at scale.** HMRC is ground truth per number; random human
audits bound the error rate (about 3/n with zero errors in n); internal
consistency rates (conflicts, unexplained mismatches, scheme-vs-age) are tracked
over time; agreement between independent sources raises confidence; and the
customer's failed invoice matches are the most direct error signal there is.

**Sources I would not use in a product.** vat-search, vat-lookup and Endole as
they are (terms forbid resale, copying or scraping; one wrong link seen); anything
built by enumerating HMRC's checker; LLM answers; scraped Google results (terms
risk); sole traders' records without a clear lawful basis. Common Crawl and
companies' own pages I would use: these are disclosures companies publish about
themselves, each verified at HMRC before it is stored.

## 6. Beyond the UK

**France: barely "discovered".** The VAT number is `FR` + a key computed from the
SIREN, and SIREN numbers are open data, so the dataset can be generated and
confirmed with VIES:

    def fr_vat(siren: str) -> str:
        key = (12 + 3 * (int(siren) % 97)) % 97
        return f"FR{key:02d}{siren}"

Belgium is similar (the VAT number is the open enterprise number). Markets where
VAT numbers derive from an open register are a join, not a discovery effort, so
they come first.

**Germany: a different problem.** Discovery is easier: the *Impressum* must
include the VAT ID when the business has one, so a corpus approach should yield
far more. Verification is harder: VIES confirms German numbers but returns no
name, and the BZSt qualified check needs a German VAT ID. The pipeline keeps its
shape, but the weak link moves from discovery (UK) to verification (Germany).
Genuinely hard countries are weak on both.

## 7. Repository and how to reproduce

    vat-discovery/
      README.md
      notes/            log.md (timestamped trail), pilot.md, aggregators.md
      src/
        vat.py          normalisation + mod-97 checksum
        explore_ch.py   first look at the Companies House snapshot
        sample.py       stratified sample (seeded, low-memory)
        analyse_cc.py   dedupe, CH join, estimates, HMRC check sheet
        sources/
          website.py      A+B: name → domain guessing (dead end, kept as evidence)
          commoncrawl.py  C: (CH number, VAT) pairs from Common Crawl WET files
      tests/            pytest: checksum, extraction, CH-number regex
      data/sample/      sample.csv (500 companies), strata_sizes.csv
      results/          cc_pairs.csv, cc_stats.csv, cc_companies.csv,
                        cc_hmrc_check.csv (manual HMRC verification), website.csv

**To reproduce** (Python 3.11+):

    python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
    python -m pip install -r requirements.txt
    python -m pytest -q
    # Companies House "BasicCompanyDataAsOneFile" (free) → unzip into data/raw/
    python src/explore_ch.py                        # Parquet + summary
    python src/sample.py                            # data/sample/sample.csv
    python -m src.sources.website --limit 10        # A+B baseline on the pilot
    python -m src.sources.commoncrawl --files 500   # ~45 min, resumable
    python -m src.analyse_cc                        # summary + results/*.csv

HMRC verification was done by hand on the public checker
(`results/cc_hmrc_check.csv`). `data/raw/` is not committed.

## 8. How I used AI

I worked with an AI assistant (Claude) throughout.

**What the AI did:** wrote most of the code (checksum, sampling, both sources,
analysis), which I ran, read and questioned when results looked wrong;
suggested some of the options I chose between (stratifying by accounts
category, the Common Crawl inversion, the CH-number regex, the extrapolation
estimates); and helped turn my log into this README.

**What I did and decided:** all the evidence gathering by hand (the pilot, 40+
HMRC checks, the ownership checks, reading the aggregators' terms and pricing);
the decisions, e.g. proposing proportional allocation and then choosing equal
allocation after comparing the trade-offs, asking whether dropping new companies
would bias the result (which became the rule *exclude what is irrelevant, never
what is merely hard to find*), raising the sample to 500, choosing Common Crawl,
not opening a vat-search account; and challenging claims: "most new companies
are inactive" did not follow from the data (log 17:57), and the API prices were
re-checked. Re-verifying the pilot numbers is also how I caught my own
Clearwater error.

The log in `notes/log.md` is the honest trail, including the wrong turns.