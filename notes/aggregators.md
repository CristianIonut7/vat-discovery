# Aggregators (source D) — desk research

**Date:** 2026-11-22, ~22:30-22:50. Manual lookups only, no scraping.
**Why:** in the manual pilot, 2 of the 5 VAT candidates came ONLY from aggregator
sites, not from the company's own website (#4 Chubb, #7 Fresh Art Club).
Both were later verified correct at HMRC. So aggregators cover exactly the cases
where website discovery fails. Questions: where do they get the numbers, how
fresh are they, what do they cost, and could a product we sell use them?

## Overview

| | vat-search.com | vat-lookup.co.uk | Endole |
|---|---|---|---|
| Operator | Linkomat GmbH, Vienna | Market Footprint Ltd ("a Datalog service") | Endole Ltd, Birmingham (CH 09346879) |
| What it is | Paid VAT ID search engine by company name/address, worldwide | UK VAT lookup by number + reverse lookup by name; claims 1.5M+ UK companies; tracks VAT groups and status changes | UK company-information / credit-report platform, 7M company profiles; shows a "VAT Number" field for some companies |
| Stated data source | "directly connected to public institutions who publish the information", but HMRC publishes no list | Not stated (cross-checks against the Datalog company database) | Generic list: Companies House, Registry Trust, Gazette, commercial data vendors, credit reference agencies, business directories, list brokers, "information found on websites in the public domain". Nothing specific for VAT |
| Freshness | API returns Status active/inactive + VAT registration/deregistration dates | "Last checked by us" date + change history; Chubb page last checked Jan 2025 (stale) | Claims real-time / daily updates; no date on the VAT field |
| Terms: commercial reuse? | **No.** Only to get the VAT ID of a specified party for a supply of goods/services; retransmission forbidden unless agreed | **No.** "Solely for personal use ... not permitted to copy any information" | **Limited.** B2B use only (due diligence, market research, identity verification, credit risk, B2B marketing); no resale right listed; user becomes data controller under UK GDPR |
| Terms: scraping? | Not explicitly; free tier blocks above ~3 requests | Copying forbidden | **Forbidden** (2.5: no scripts, scrapers or crawlers); automated delivery only via a paid API licence (3.2) |
| Sells API / bulk? Price? | Yes, JSON API, ~0.045-0.95 EUR per search; also full-service "VAT cleansing" | Not seen | Yes, paid API licence (price not public); web plans from £25/month, exports 1,000 rows/month |
| Accuracy warranty | None | None | None ("as is") |
| Coverage on my 3 known positives | Not tested (no account) | 0/3 by name; by number: found, but linked to the WRONG CH entity | 1/3 (#7 only) |

## vat-search.com

**Terms (GTC version 26 Oct 2026):**
- Operator: Linkomat GmbH, Vienna (FN452179w). Also runs VAT-Search.co.uk,
  VAT-Search.eu, TVA-Recherche.eu, UID-Suche.eu.
- Service: VAT ID search **by company name or address**, plus validation and
  master-data cleansing/enrichment. So name → VAT discovery already exists
  commercially, as a lookup service (not as a sellable dataset).
- Free account: limited reveals; a user may be blocked above 3 requests per 168 hours.
- Usage restriction: only to obtain the VAT ID of a specified party in connection
  with a supply of goods/services; any other use and retransmission is forbidden
  unless agreed → **cannot be resold inside a dataset product without a licence deal.**
- No warranty that the data is correct. Data source not stated.

**Pricing page:**
- Search index claims: 150M+ companies, 28 European + 13 non-European countries
  (paid); 70M+ (free). UK coverage not stated separately.
- API: 1 credit per name/address search that returns ≥1 result, VAT numbers
  included. Validation of a given number: 0.1-0.2 credits.
- Packages: from 19 EUR for 20 credits/year (~0.95 EUR/credit) down to
  299 EUR for 5,000 credits/month (~0.06 EUR/credit); prepaid yearly
  2,691 EUR for 60,000 credits (~0.045 EUR/credit).
- Free tier: 3 test credits every 30 days (the terms say block above 3 requests
  per 168h; inconsistent, both tiny).
- Claims 600+ clients (Amazon, D&B, KPMG, FedEx...); TeamViewer uses the API in
  its order process.
- **"Full-Service VAT Cleansing":** the customer sends a company list; matching is
  semi-automatic, trained specialists handle unclear cases and report companies
  that are dissolved or not required to register; success-based fee.

**About page + API docs:**
- Claims **21,028,000+ UK VAT IDs** (228M worldwide). Active UK registrations
  ≈ 2.18M (brief) → ~10× more numbers than active registrations.
- Checksum-valid 9-digit GB numbers ≈ 10^7 prefixes × 2 schemes ≈ 20M
  → their UK count is close to the WHOLE valid number space.
- Stated source: "directly connected to public institutions who publish the
  information". HMRC publishes no list; its checker only answers for a given
  number.
- **INFERENCE (not proven):** the UK index was built by systematically querying
  the HMRC checker over checksum-valid numbers, keeping inactive ones too (the
  API returns Status active/inactive and VATDeregistrationDate). Alternative:
  all numbers ever issued over ~50 years; that too requires querying the
  checker. Either way, enumeration of HMRC is not hypothetical, it is a product
  (→ debate topic 1).
- API parameter `crnr` = company register number, "currently only available for
  cc=gb" → direct CH number → VAT lookup, exactly the customer's join.
- API `eori` check: example "GB12345678000" = GB + 9 digits + "000"; "in the UK
  there often are returned more than one EORI numbers" → supports H3 (EORI
  embeds the VAT number).
- Matching is probabilistic: Score > 3 = close match.
- Includes sole traders (names, home addresses); deletes on request → GDPR
  exposure for any product redistributing this data.

**Decision:** no account created. The terms already answer the key question
(no resale without a licence; free tier ~3 lookups), so a 3-company coverage test
adds little. Search without an account is not possible (tried), so its coverage on my
sample remains **unmeasured**: a stated limitation.

## vat-lookup.co.uk

- Homepage: supports lookup by VAT number AND **reverse lookup by company name**.
  → My earlier hypothesis ("checker only") was WRONG.
- Claims VAT details for **1.5M+ UK companies** (vs ~2.18M active UK
  registrations incl. sole traders; my target population ≈ 3.58M companies).
- Tracks "multiple companies sharing single VAT numbers" (= VAT groups, as found
  for Argos / Go Outdoors), related companies, pan-European registrations and
  VAT status changes. Cross-checks against the "Datalog" company database.
- **Name search:** #1 British Arab Commercial Bank, #4 Chubb, #7 Fresh Art Club
  → none found (0/3), although all three numbers exist and are verified.
- **Lookup by number** (GB668395969, Chubb). The page shows:
  - "Last checked by us: 2025-01-29" + a change history since 2019 → they
    RE-POLL HMRC periodically and diff the results (= a refresh strategy, see
    debate topic 2).
  - Stale: their latest address is 100 Leadenhall St; HMRC today (Nov 2026)
    returns 40 Leadenhall St.
  - VAT-registered name history: Chubb European Group Ltd → Chubb Services UK
    Ltd (2020) → ... → "COURTIERS GROUP HOLDINGS LIMITED" for one month (2024)
    → back to Chubb Services UK Limited. Registered names are volatile → name
    matching at the wrong moment fails.
  - **Wrong CH link:** they attach the number to CHUBB EUROPEAN GROUP PLC
    (CH 01112892, "Converted / Closed", with their own warning), not to CHUBB
    SERVICES UK LIMITED (CH 01509033, confirmed on Endole). → an aggregator's
    VAT↔CH join is exactly the invisible false positive from the brief. VAT
    numbers can move between legal entities (reorganisations, VAT groups).
  - "Issued before November 2009" → issue period inferred from the number
    (see checksum-scheme note below).
  - Also lists VAT numbers of other companies at the same postcode and of
    "companies with common directors" → they hold bulk VAT data.
- Terms (footer): "solely for the purpose of allowing persons involved in the
  supply of goods or services to validate the authenticity of VAT numbers ...
  solely for personal use ... not permitted to copy any information."
  → not usable in a product.

## Endole

- **#7 Fresh Art Club:** VAT GB492114011 shown free, in a "VAT Number" field on
  the company page.
- **#4 Chubb Services UK Limited:** page shows CH no. 01509033 (active, large,
  part of a 35-company Chubb group, PSC Chubb London Services Ltd) and address
  40 Leadenhall St (matches HMRC today). **No VAT number shown.**
- **#1 British Arab Commercial Bank:** no VAT number shown.
- → 1/3 on companies whose VAT numbers exist and are verified: partial,
  unexplained coverage.
- Data sources (privacy policy): Companies House, Registry Trust, Gazette,
  third-party business intelligence providers and commercial data vendors,
  credit reference agencies, business directories, company list brokers,
  "information found on websites in the public domain". No specific source
  for VAT numbers.
- Claims 7M company profiles, "real-time" / daily updates.
- Terms of Use:
  - 2.5: no access by automated scripts, scrapers or crawlers (except search
    engines);
  - 3.2: automated data delivery only through separate, paid API licences;
  - 4.2: B2B data only for due diligence, market research, identity
    verification, credit risk and B2B marketing; no resale right listed;
  - 4.3: the user becomes the independent data controller (UK GDPR);
  - 8.1: data provided "as is", no accuracy warranty.
- Pricing: web plans from £25/month (exports 1,000 rows/month per user);
  API access as a separate paid licence (price not public).

## Access tests

| # | Company | vat-search | vat-lookup | Endole |
|---|---------|-----------|-----------|--------|
| 1 | BRITISH ARAB COMMERCIAL BANK PLC | blocked (login) | by name: not found | no VAT shown |
| 4 | CHUBB SERVICES UK LIMITED | not tested (no account) | by name: not found; by number: found, but linked to the WRONG CH entity | no VAT shown |
| 7 | FRESH ART CLUB LTD | not tested (no account) | by name: not found | GB492114011 shown free |

A full coverage table on all 10 pilot companies turned out not to be feasible:
one source needs a paid account, one cannot search by name.

## HMRC checks of aggregator-only numbers

- #4 Chubb GB668395969 → VALID, registered to CHUBB SERVICES UK LIMITED,
  40 Leadenhall St, London EC3A 2BJ. CH address matches.
- #7 Fresh Art Club GB492114011 → VALID, registered to FRESH ART CLUB LTD,
  Station View House, 41 Brunswick Road, Shoreham-by-Sea BN43 5WA.
  CH address matches. Checked 22 Nov 2026, 20:33 GMT.

→ 2/2 aggregator-only numbers verified correct. Neither is published on the
company's own website.

## Side finding: checksum scheme ≈ issue period

vat-lookup labels Chubb's number "Issued before November 2009". Classifying the
8 real numbers I hold with src/vat.py: old scheme (%97 == 0) for Chubb, BACB,
Argos, Go Outdoors, Currys; new scheme (+55) for Fresh Art Club (incorporated
2024), Thunder Energy (new company), Clearwater. All consistent with the new
scheme starting in Nov 2009. Cheap plausibility check: a company incorporated
after 2010 holding an old-scheme number is probably using another entity's
number (a VAT group, e.g. Go Outdoors → JD Sports) or the number is wrong.
Observation on 8 numbers, not a proven rule.

## Implications

1. **Benchmark for Part 3.** The customer could fill its ~26.7k missing VAT
   numbers (2/3 of 40k suppliers) itself, for roughly 1.2-1.6k EUR in vat-search
   credits: its own use is allowed by the terms, resale by us is not. Our product
   has to beat that on price, coverage, freshness or bulk delivery.
2. **Name → VAT discovery is solved commercially as a lookup service**, with
   humans in the loop for the hard cases. Nobody sells the open dataset because
   the terms forbid redistribution.
3. **Debate topic ("which sources would you not use in a product we sell?"):**
   vat-search as-is (redistribution forbidden, data source unstated, no accuracy
   warranty). Usable only through a licence or partnership.
4. **How aggregators get numbers.** None of them says. The strongest evidence is
   vat-search's 21M UK numbers ≈ the whole checksum-valid space (~20M), plus
   vat-lookup's periodic re-checks against HMRC → systematic querying of the
   HMRC checker is the most plausible mechanism (inference, not proven).
5. **Aggregator joins are themselves a false-positive source.** vat-lookup ties
   Chubb's number to a closed entity. Taking an aggregator's VAT↔CH link at face
   value would import that error invisibly → any aggregator data needs the same
   identity checks as web data.
6. **None of the three can be used in a product we sell** without a licence:
   vat-search forbids retransmission, vat-lookup forbids copying, Endole forbids
   scraping and limits use to listed B2B purposes. None warrants accuracy.