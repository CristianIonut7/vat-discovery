# Work log

## 2026-11-22

**16:00** Started. Read the brief. Initial framing before any code:
- The deliverable is a *feasibility answer* (can a UK VAT dataset be built from
  the open web, at what cost, where does it break), not a scraper.
- Key asymmetry: HMRC verifies a VAT number but never discovers one.
  → every pipeline must be "find candidate somewhere → verify at HMRC".
- "Not found" is ambiguous: not VAT-registered vs. I failed to find it.
  Need to report these separately, not as one number.
- A wrong number is worse than a missing one → precision matters more than
  coverage. Need a rule for "this VAT number belongs to THIS company".

**16:30** Setup: GitHub repo, venv, folder structure, .gitignore
(data/raw and .env excluded).

**16:45** HMRC Developer Hub: account + application created.
- "Check a UK VAT number" API v2 requires OAuth (application-restricted token),
  so it is not an anonymous endpoint.
- Client secret is shown only once; had to regenerate it.
- New applications are sandbox-only. Sandbox returns test data, not real
  registrations → useless for verifying real candidates.

**16:58** DECISION: no production API for this PoC.
- Why: production access needs a separate request + approval; today is Sunday,
  submission was planned for tonight → won't be approved in time.
- Instead: verify candidates via the public web checker
  (gov.uk/check-uk-vat-number), which returns validity + registered
  name and address.
- Consequences:
  - verification throughput is low (manual / slow) → caps my sample size
    and the number of candidates I can verify;
  - I should filter candidates hard (format + checksum) BEFORE using the
    checker, so no checks are wasted on garbage;
  - for Part 3: at scale, production API access is a hard prerequisite;
    note rate limits and the terms of use as constraints.

### Hypotheses to test (not yet verified)
- H1: GB VAT numbers (9 digits) have a mod-97 checksum → can filter
  regex false positives (phone numbers, order IDs).
- H2: The VAT number is NOT derivable from the Companies House number
  → UK is a pure discovery problem (unlike e.g. France).
- H3: GB EORI numbers for VAT-registered businesses embed the VAT number
  → possible adjacent-identifier route.
- H4: Companies with websites that sell online are legally required to show
  their VAT number → website footers / terms pages are a candidate source.
  Open question: CH has no websites, how do I get from company → domain?

**17:04** Tried to request production credentials. It is a full compliance
questionnaire (organisation details, development practices, a named
"responsible individual" accountable for the terms of use), followed by
manual review. Progress expires after 6 months.
→ Not feasible for a weekend PoC as an individual. Did not submit.
→ Part 3 note: production API access for a commercial product means
  organisational onboarding + terms-of-use compliance, not just an API key.
  Need to check whether the terms allow bulk / commercial re-verification
  (relevant for the brute-force debate topic too).

**17:08** Downloaded Companies House BasicCompanyDataAsOneFile-2026-11-01.zip
into data/raw/ (not committed).

**17:10** src/vat.py: normalise() + mod-97 checksum (both schemes: %97==0
and +55) + validate() returning a reason (ok / bad_format / bad_checksum).
Deliberately out of scope: 12-digit branch numbers, GD/HA prefixes.
XI (Northern Ireland) treated like GB.
Tests: format variants, rejects, both schemes, single-digit typo catch rate
(>95%, not 100%, because two schemes means some typos land on a valid number).

**17:20** Collected 4 real-world VAT numbers from public pages:
- Argos Ltd (CH 01081551), "660 4548 36", argos T&Cs → checksum ok
- Go Outdoors (CH 12659342), "GB787440102", gooutdoors.co.uk/terms → checksum ok
- Currys (eBay seller profile), "GB 226659933" → checksum ok
- TES Consumer Solutions Ltd (eBay listing T&Cs), "173140925GB" → bad_format:
  "GB" written as a SUFFIX. Real-world format variant my normaliser missed.
NOT YET verified on HMRC checker.

Observations while searching:
- eBay shows "Business details: VAT number" for business sellers → possible
  source, but only covers companies that sell on eBay.
- Argos: aggregator sites list an HMRC address (Milton Keynes, tax dept)
  different from the registered office → address matching may be unreliable.
  To confirm on HMRC checker.
- Aggregators like vat-search.com already exist (cite HMRC checker + CH as
  sources) → contradicts "nobody sells it"; investigate later.

**17:29** Fixed normaliser: also strips a trailing "GB" (real-world variant,
found on the TES Consumer Solutions listing). Added the 4 real numbers as
test cases → 10/10 tests pass.
Lesson: format variants come from real pages, not from the spec. Expect more
(e.g. "GB 123 4567 89", "VAT: 123456789") when extracting at scale.

DECISION: not handling 12-digit / GD / HA formats.
- GD (government departments) and HA (health authorities) are not companies
  on the Companies House register → outside the customer's target population.
- 12-digit numbers = the same 9-digit VAT number + a 3-digit branch suffix;
  the company-level identifier is the first 9 digits. If I meet them during
  extraction, I can take the first 9 digits. Not worth building now.

**17:34** Verified the 4 numbers on the HMRC web checker:

| Found on                            | HMRC name                    | HMRC address           | Result |
|-------------------------------------|------------------------------|------------------------|--------|
| Argos T&Cs                          | SAINSBURY'S SUPERMARKETS LTD | 33 Charterhouse St     | valid  |
| Go Outdoors T&Cs                    | JD SPORTS FASHION PLC        | Hollinsbrook Way, Bury | valid  |
| Currys eBay profile                 | CURRYS GROUP LIMITED         | 1 Portal Way, Acton    | valid  |
| TES Consumer Solutions eBay listing | -                            | -                      | NOT FOUND (checksum ok) |

KEY FINDING: VAT groups. 2/3 valid numbers are registered to the PARENT
(Sainsbury's for Argos, JD Sports for Go Outdoors), not the company that
publishes them. A name-only match rule would flag 2 correct numbers as false
positives. For the customer the group number IS the right one: it's what
appears on the supplier's invoices.
→ "Correct" must be defined as "the number this company invoices under",
  not "HMRC name == CH name".
→ Matching needs a third outcome: name mismatch but address matches /
  parent-subsidiary link (Companies House PSC data could confirm the parent).
- Address matched the publishing company's registered office in both cases;
  the aggregator's Argos address (Milton Keynes) was stale.
- Checksum-valid ≠ registered: TES number passes checksum, HMRC has no record
  (deregistered? typo on page? stale listing?).
- Web checker: no captcha or rate limit observed so far.

**17:48** Explored CH snapshot 2026-11-01: 5,711,779 rows, 5,179,256 Active
(+417k "proposal to strike off"). Brief says ~4.2M live; to explain.
- 1.27M active companies incorporated 2025-2026 (~25%). Their activity is
  UNKNOWN (see 17:57).
- DORMANT 557k → almost certainly not VAT-registered.
- NO ACCOUNTS FILED 1.34M → initially assumed inactive; corrected at 17:57.
- Top SIC: residential letting / real estate / holding cos / residents'
  management → typically VAT-exempt or not trading.
- 47910 internet retail: 148k → most likely to publish VAT (legal duty online).
- No website column → company→domain is a separate problem.
Implication: a single coverage number over "all active" is misleading.
Need stratified sample + per-stratum reporting. Customer's suppliers
(trading B2B firms) ≠ random CH company.

**17:57** Verified: NO ACCOUNTS FILED × incorporation year (active):
2026: 650,056 | 2025: 525,457 | 2024: 22,000 | 2023: 24,656 | 2022: 14,792
→ ~88% of "NO ACCOUNTS FILED" are 2025-26 incorporations: a timing effect
  (first accounts due ~21 months after incorporation), not a size/activity
  signal.
→ Treat it as a "new company, size unknown" stratum. The ~70k older ones are
  late filers / anomalies.
(Corrected my earlier assumption that new companies are mostly inactive:
the data does not show that.)

**18:15** SAMPLING DESIGN — decisions:
Principle: exclude only what is IRRELEVANT to the customer (cannot be a
supplier issuing invoices), never what is merely HARD to find.

Base population:
- CompanyStatus = 'Active' only. Excluded: proposal to strike off,
  liquidation, administration, receivership (being closed / insolvent).
  Note: some companies in administration keep trading; ~4k, excluded for
  simplicity.
- CompanyCategory: Private Limited, PLC, LLP only.

Excluded as irrelevant (but sampled in a CONTROL group to test the
assumption):
- AccountCategory = DORMANT (no significant transactions → no VAT turnover).
  A dormant company may start trading later → that's a dataset refresh issue,
  not a sampling issue.
- SIC 68xxx (real estate), 64209 (holding cos), 98000 (residents' mgmt),
  99999 (dormant).
- The SIC filter uses ALL 4 SIC codes: a company counts as irrelevant only if
  EVERY supplied code is in the excluded list. E.g. 68100 + 47910 still
  trades → kept.

Kept:
- New companies (2025-26, NO ACCOUNTS FILED) → own stratum. Excluding them
  would remove the hard cases and inflate coverage; the customer also
  onboards new suppliers.
- SIC "None Supplied" (217k) → kept; a missing field is not evidence of
  irrelevance.

No sector filter: we don't know the customer's real supplier list
(a manufacturer also buys IT, cleaning, catering...). Instead, keep SIC in the
sample and analyse coverage by sector afterwards.

Reproducibility: the sample is drawn with a fixed random seed, so anyone can
regenerate exactly the same 500 companies from the same CH snapshot.

**18:20-18:32** SAMPLE SIZE AND ALLOCATION — decisions:

Strata (by Accounts.AccountCategory, after the filters above):

| Stratum      | Definition                                                         |
|--------------|--------------------------------------------------------------------|
| micro        | MICRO ENTITY                                                       |
| small_exempt | TOTAL EXEMPTION FULL                                               |
| small        | SMALL, UNAUDITED ABRIDGED, AUDITED ABRIDGED, TOTAL EXEMPTION SMALL |
| large        | FULL, MEDIUM, GROUP, AUDIT EXEMPTION SUBSIDIARY                    |
| new          | NO ACCOUNTS FILED and incorporated 2025-2026                       |
| control      | random draw from what I EXCLUDED as irrelevant (dormant + SIC 68xxx / 64209 / 98000 / 99999) |

Left out (small): ACCOUNTS TYPE NOT AVAILABLE, PARTIAL EXEMPTION, FILING
EXEMPTION SUBSIDIARY, and ~70k pre-2025 companies with no accounts filed
(late filers / anomalies).

Sample size: 500 companies (initially planned 200).
- HMRC verification is manual (web checker), but it only applies to numbers I
  FIND, not to every company. If coverage is low (my guess: 10-40%), 200
  companies would give too few verified numbers to say anything per stratum.
- The real bottleneck is also the search per company (finding the website or
  another place where the number appears), not only verification.
- So I draw 500, SHUFFLE the processing order and work through it until time
  runs out. Any prefix of a randomly ordered list is still a random sample,
  so stopping early does not bias the result; it only reduces precision.

Allocation: considered three options.
1. Proportional to population size. Rough shares: micro 38%, small_exempt 28%,
   new 26%, small 5%, large 3%. With 470 companies → large ≈ 15, small ≈ 23.
   + sample looks like the population, overall coverage is read directly and
     is slightly more precise.
   - large/small strata too small to conclude anything (e.g. 7/15 found →
     confidence interval roughly 20%-70%). It gets worse if I stop early:
     at 200 processed, only ~6 large companies.
   - large companies are exactly the ones most relevant to a manufacturer's
     supplier base, which is not shaped like the CH register.
2. Proportional with a floor (min 40 per stratum). A compromise, but harder to
   explain and adds nothing essential over option 3.
3. Equal allocation. CHOSEN: 5 strata × 94 + 30 control = 500.
   + every stratum is measurable on its own → answers the real question of the
     brief: WHERE discovery works and where it breaks (e.g. "feasible for large
     companies, not for micro").
   - sample over-represents large companies → overall coverage must be
     REWEIGHTED by the true stratum sizes (saved by the sampling script).
     Slightly less precise overall number than proportional.
Why: the goal is not one headline number but understanding how feasibility
varies by company type; per-stratum precision matters more here.

**19:10** sample.py hit Out of Memory on the full snapshot; ran after freeing
RAM (~95% used). Replaced with a low-memory version (only the 16 needed
columns, drop intermediate tables, spill to disk). Same deterministic sample.

**19:11** Sample drawn (data/sample/sample.csv, 500 rows, shuffled order).
Population per stratum (data/sample/strata_sizes.csv):
micro 1,384,125 (38.7% of target) | new 959,573 (26.8%) |
small_exempt 956,898 (26.7%) | small 173,214 (4.8%) | large 107,347 (3.0%)
Target population ≈ 3.58M. Excluded as irrelevant ≈ 1.22M (control group).
Left out ≈ 14k (negligible).
Sanity bound: ~2.18M VAT registrations nationally INCLUDING sole traders
vs 3.58M target companies → coverage can never approach 100%.
TODO: find HMRC stats on VAT registrations by legal form → realistic ceiling.

**~20:50-21:25** Manual pilot on the first 10 companies by process_order
(details: notes/pilot.md). Notes taken along the way:

- #4 Chubb Services UK Ltd: no own website (uses group site chubb.com), no VAT
  number shown. Gemini cited the aggregator vat-lookup.co.uk as source; that
  page did not load for me.
  HMRC check: GB668395969 → CHUBB SERVICES UK LIMITED, 40 Leadenhall St,
  London EC3A 2BJ. CH address matches → name + address match.
  Gemini was right here, but n=1 proves nothing about LLM reliability.
  KEY: number NOT on company's own site, yet the aggregator has it.
  Hypotheses for how aggregators get numbers: (a) invoices / public documents,
  (b) systematic enumeration of HMRC checker with checksum-valid numbers
  (see debate topic). Unknown → investigate their stated sources.
- #5 Christopher Topco Ltd: SIC 56101 (restaurants), but "Topco" = holding at
  the top of a group. Holding companies can declare the group's operating SIC
  → SIC-based exclusion misses them. Name patterns (Topco/Midco/Bidco/Holdings)
  could flag them. Large stratum likely over-represents holdings/subsidiaries
  (VAT groups) → expect lower "own number" discovery there.
- #6 LGSL Online Ltd: site found via Gemini, but no CH number or address on it
  → can't link it to the company.
  IDEA: CH company number on the same page/site as the VAT number = strong
  identity anchor (legally required on UK company websites). Use it to accept
  a candidate, instead of fuzzy name matching → reduces false positives.
- #7 Fresh Art Club: VAT GB492114011 only on Endole (commercial company-data
  aggregator); own site (freshartclub.com) shows neither VAT nor CH number.
  Endole's CH number matches the sample. Not yet verified at HMRC.
- #10 Blue Jay of London: no site; Gemini offered VAT numbers of SIMILARLY
  named companies (BluJay Solutions, Bluejay Homes) → concrete false-positive
  trap for name matching.
- DECISION: LLM answers (Gemini) are not a source. Only a page I can cite
  counts; LLM output is logged separately.

**21:25** Manual pilot done, ~25 min.
- Candidate VAT found: 5/10 (3 own website, 2 aggregators only).
- Website found: 6/10; confirmed by CH number on site: 4 (#1, #2, #3, #9).
- Nothing at all: 4/10 (holding with no site, new companies, small firms).
- ~2.5 min/company manually → 500 companies ≈ 21h; doesn't scale.
Findings:
1. Discovery = 3 sub-problems: company→website (hard),
   website→VAT (easy when present: footer / T&Cs), aggregators.
2. Aggregators (vat-lookup, Endole, vat-search) hold numbers companies don't
   publish themselves (#4 Chubb, verified at HMRC; #7 Fresh Art Club).
3. Name matching is dangerous: for #10 Gemini offered VAT numbers of
   similarly-named companies. CH number on the page = identity anchor.
4. n=10: signals only, not rates.

**21:29** Checked #1-#3: CH number appears on all three sites.
→ In 3/3 own-website finds, VAT number and the correct CH number are on the
  same site. Rule "accept VAT only if the company's CH number is on the
  same site" would keep all 3 good finds and reject the #10 trap.



  **21:45** DECISION: what to automate next. Options considered:
- A+B (guess domain from name → fetch homepage + legal pages → extract VAT,
  accept only if CH number on same site). Code written (src/sources/website.py).
  My doubt: domain guessing misses many sites (e.g. #9 is ingr.tech, not
  guessable from the name). Expect high precision, low coverage.
- C (Common Crawl). Invert the problem: instead of company → site → number,
  scan a random slice of the crawl once and extract every (CH number, VAT
  number) pair co-occurring on the same page. This is the "bulk corpus"
  shape the brief hints at.
- D (aggregators: vat-lookup, Endole, vat-search). Document coverage,
  stated sources, freshness, terms of use. No bulk scraping.

PLAN:
1. A+B on the 10 pilot companies only, as a baseline against my manual
   results (~5 min). If it fails, that's a documented dead end with evidence.
2. C as the main experiment: ~10-20 WET files (random slice of one monthly
   crawl). Measure: yield (pairs per million pages), precision (HMRC check
   on a subsample of pairs), extrapolation to the full crawl → coverage and
   cost per company at scale (Part 3).
   Caveat: on ~20 of ~100k files, almost none of my 500 sample companies will
   appear. C measures CORPUS YIELD, not sample coverage; report the two
   separately.
3. D at the end (~30 min, desk research).


**21:51** A+B baseline on the 10 pilot companies → 0/3 of my manual
own-website finds recovered; 2 sites found, both unconfirmed
(freshartclub.co.uk, lgslonline.com). Note: script found freshartclub.co.uk,
I had found freshartclub.com → same name, two domains: name is not identity.

Why it failed (real domains from the pilot):
| # | Company                          | Real domain                              | Failure mode |
|---|----------------------------------|------------------------------------------|--------------|
| 1 | British Arab Commercial Bank PLC | bacb.co.uk                               | acronym |
| 2 | Clearwater Servicing Ltd         | clearwaterltd.com, clearwaterchemicals.co.uk | brand name ≠ legal name, 2 domains |
| 3 | Thunder Energy Services Ltd      | thunderenergy.co.uk                      | generic word dropped ("Services") |
Fetch test on thunderenergy.co.uk: [OK] → [failure is domain
guessing, not blocking].

DEAD END: name → domain guessing. Even with variants (dropping generic words)
it would recover at most 1/3 here; acronyms and brand names are not derivable
from the CH name. The company→website step needs a different shape:
a search engine (paid API at scale) or a corpus where the CH number itself
leads to the page → Common Crawl (C).
Kept the CH-number identity check: it correctly refused to trust the two
name-matched sites.


**22:05** Common Crawl test, crawl CC-MAIN-2026-43 (100,000 WET files),
2 random files (seeded), ~42k pages, ~5s/file streamed (no disk).
- ~1% of pages mention "VAT"; 74 pages carry a checksum-valid VAT number.
- 62 pages carry BOTH a labelled CH number and a VAT number (~84% of pages
  with a VAT number) → the CH-number identity anchor is usually available.
- Yield ≈ 1.5 pair-pages per 1,000 pages. Naive extrapolation to the full
  crawl ≈ 3M pair-pages, but many will be duplicates (same company on several
  pages) or multi-company directory pages → need unique-company count.
- Next: 200 files (~0.2% of the crawl), then dedupe, join with CH register,
  HMRC-check a random subsample of pairs for precision.


  **22:13** Started Common Crawl run: 200 files, then stopped (Ctrl+C) at ~70
and restarted with 500. Same seed → the first 200 of the 500 list are the
same files; finished files are skipped. The file interrupted mid-way is
reprocessed → some duplicate pairs in cc_pairs.csv, removed at analysis.

**22:30-22:50** Source D: aggregators desk research (notes/aggregators.md).
- #7 Fresh Art Club GB492114011 verified at HMRC: name + address match.
  → 2/2 aggregator-only numbers correct (#4, #7).
- vat-search.com (Linkomat GmbH, Vienna): paid VAT search BY NAME, API,
  ~0.045-0.95 EUR per search; terms forbid retransmission / other use without
  agreement → not resellable in our product. Also sells "full-service VAT
  cleansing" with human specialists = exactly the customer's problem.
- vat-lookup.co.uk: no search by name; looks like a checker whose result pages
  get indexed by Google (hypothesis).
- DECISION: no vat-search account (terms answer the key question; free tier
  ~3 lookups). Coverage of this source stays unmeasured.
- KEY for Part 3: the customer could fill its ~26.7k missing numbers itself for
  ~1.2-1.6k EUR via vat-search credits. Our product must beat that.

  **22:49** vat-search About + API docs: claims 21M+ UK VAT IDs vs ~2.18M active
registrations ≈ the entire checksum-valid number space (~20M) → strong
inference that HMRC's checker was enumerated (incl. inactive numbers).
API supports lookup by CH number (crnr, GB only) and EORI checks
(GB + VAT + 000, supports H3). Sole traders included → GDPR issue.


**23:00** vat-lookup.co.uk. Homepage claims reverse lookup by name and VAT
data for 1.5M+ UK companies (my "checker only" hypothesis was wrong).
Name search: 0/3 found (#1, #4, #7), although all three numbers exist.
Lookup by number (Chubb GB668395969):
(1) links the VAT number to the WRONG CH entity: Chubb European Group PLC
    (01112892, closed), not Chubb Services UK Ltd (01509033, my sample)
    → aggregator joins carry the invisible false-positive risk;
(2) stale: last checked Jan 2025, address changed since (HMRC today: 40
    Leadenhall St);
(3) volatile registered names (incl. a one-month "Courtiers Group Holdings");
(4) re-polls HMRC and diffs the results = a refresh strategy in the wild.
Observation: checksum scheme ≈ issue period (new "+55" scheme from Nov 2009);
consistent on all 8 real numbers I hold → cheap plausibility check: company
incorporated after 2010 + old-scheme number → probably a group's / another
entity's number. Terms forbid copying → not usable in a product.

**23:04** Endole: VAT shown for #7 only (1/3 known positives); confirms Chubb
Services UK = CH 01509033. Terms forbid scraping (2.5), automated delivery
only via paid API licence (3.2), B2B-only uses, no accuracy warranty.
VAT data source not stated.
vat-search: search impossible without an account → coverage unmeasured.

Source D closed (notes/aggregators.md). Conclusions:
- Aggregators cover cases websites don't (2/2 aggregator-only numbers
  correct), but coverage is partial and unexplained (vat-lookup 0/3 by name,
  Endole 1/3).
- None is usable in a product without a licence (vat-search: no
  retransmission; vat-lookup: no copying; Endole: no scraping, listed B2B
  uses only). None warrants accuracy.
- Aggregator VAT↔CH joins can be wrong (Chubb) → need the same identity
  checks as web data.
- vat-search's 21M UK numbers ≈ the whole checksum-valid space →
  enumeration of the HMRC checker is the most plausible mechanism (inference).
- Benchmark: the customer could buy ~26.7k lookups for ~1.2-1.6k EUR itself.