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

**17:08** Downloaded [text](../data/raw/BasicCompanyDataAsOneFile-2026-11-01.zip)

### TODO
- Download Companies House BasicCompanyData snapshot, record date + row count.
- Implement + test checksum (H1).