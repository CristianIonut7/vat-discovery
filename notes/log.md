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
  submission is due tonight → won't be approved in time.
- Instead: verify candidates via the public web checker
  (gov.uk/check-uk-vat-number), which returns validity + registered
  name and address.
- Consequences:
  - verification throughput is low (manual / slow) → caps my sample size
    and the number of candidates I can verify;
  - I should filter candidates hard (format + checksum) BEFORE using the checker,
    so no checks are wasted on garbage.
  - For Part 3: at scale, production API access is a hard prerequisite;
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
  submission is due tonight → wontime.

**17:04** Tried to request production credentials. It is a full compliance
questionnaire (organisation details, development practices, a named
"responsible individual" accountable for the terms of use), followed by
manual review. Progress expires after 6 months.
→ Not feasible for a weekend PoC as an individual. Did not submit.
→ Part 3 note: production API access for a commercial product means
  organisational onboarding + terms-of-use compliance, not just an API key.
  Need to check whether the terms allow bulk / commercial re-verification
  (relevant for the brute-force debate topic too).


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
  different from the registered office → address matching may be unreliable,
  name matching matters more. To confirm on HMRC checker.
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
| Found on              | HMRC name                    | HMRC address        | Result |
|-----------------------|------------------------------|---------------------|--------|
| Argos T&Cs            | SAINSBURY'S SUPERMARKETS LTD | 33 Charterhouse St  | valid  |
| Go Outdoors T&Cs      | JD SPORTS FASHION PLC        | Hollinsbrook Way, Bury | valid |
| Currys eBay profile   | CURRYS GROUP LIMITED         | 1 Portal Way, Acton | valid  |
| TES Consumer Solutions eBay listing | -              | -                   | NOT FOUND (checksum ok) |

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
- Web checker: at the moment there was no captcha or fill limit


**17:08** Downloaded [text](../data/raw/BasicCompanyDataAsOneFile-2026-11-01.zip)

**17:48** Explored CH snapshot 2026-11-01: 5,711,779 rows, 5,179,256 Active
(+417k "proposal to strike off"). Brief says ~4.2M live; to explain.
- 1.27M active companies incorporated 2025-2026 (~25%). Their activity is
  UNKNOWN: "NO ACCOUNTS FILED" is likely a timing effect (first accounts due
  ~21 months after incorporation), not evidence of inactivity. [verify with
  year × AccountCategory]
- DORMANT 557k + NO ACCOUNTS FILED 1.34M → large share almost certainly
  not VAT-registered.
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
  (first accounts not yet due), not a size/activity signal.
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
| Stratum       | Definition                                                        |
|---------------|-------------------------------------------------------------------|
| micro         | MICRO ENTITY                                                      |
| small_exempt  | TOTAL EXEMPTION FULL                                              |
| small         | SMALL, UNAUDITED ABRIDGED, AUDITED ABRIDGED, TOTAL EXEMPTION SMALL|
| large         | FULL, MEDIUM, GROUP, AUDIT EXEMPTION SUBSIDIARY                   |
| new           | NO ACCOUNTS FILED and incorporated 2025-2026                      |
| control       | random draw from what I EXCLUDED as irrelevant (dormant + SIC     |
|               | 68xxx / 64209 / 98000 / 99999)                                    |
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

SIC filter uses ALL 4 SIC codes: a company counts as irrelevant only if EVERY
supplied code is in the excluded list (68xxx/64209/98000/99999). E.g. 68100 +
47910 still trades → kept.

Reproducibility: fixed random seed.



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