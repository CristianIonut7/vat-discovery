# Manual pilot — first 10 companies (process_order 1-10)

**Date:** 2026-11-22, ~20:50-21:25 (~25 min, ~2.5 min/company)
**Goal:** before writing any discovery code, find out by hand where VAT numbers
actually show up, which sources are worth automating, and what goes wrong.
**Method:** for each company, in order: Google (`"NAME" VAT`, `"NAME" "VAT number"`,
Google's Gemini AI Overview included), then the company's website (footer, T&Cs,
contact, privacy), then search by Companies House (CH) number. Max ~3-4 min/company.
Candidates are **not** counted as found until verified on the HMRC checker.

## Results

| # | Company | Stratum | Website | VAT candidate & source | Min | Notes |
|---|---------|---------|---------|------------------------|-----|-------|
| 1 | BRITISH ARAB COMMERCIAL BANK PLC | large | yes, 1st search result | GB397172124, company website | 1 | CH no. on site matches → **confirmed** |
| 2 | CLEARWATER SERVICING LTD | micro | yes, 3rd search result | GB207409622, website footer | 2 | CH no. on site matches → **confirmed** |
| 3 | THUNDER ENERGY SERVICES LTD | new | yes | GB518641484, terms of service page | 2 | CH no. on site matches → **confirmed**. New company that does publish its VAT. |
| 4 | CHUBB SERVICES UK LIMITED | large | no own site, uses group site (chubb.com) | GB668395969, via Gemini → aggregator (vat-lookup.co.uk, page did not load) | 4 | Not on company site. **HMRC: CHUBB SERVICES UK LIMITED, 40 Leadenhall St, EC3A 2BJ → name + address match CH.** |
| 5 | CHRISTOPHER TOPCO LIMITED | large | no own site; only CH-data aggregators (companycheck, formationdata) | none | 2 | SIC 56101 (restaurants) but name = "Topco" → holding at top of a group, declares the group's SIC; SIC filter can't catch it. Likely in a VAT group → "not found" probably correct. |
| 6 | LGSL ONLINE LTD | new | lgslonline.com (via Gemini), **unconfirmed**: no CH no., no address on site | none | 3 | Can't link site to company. UK law requires CH details on company websites → absent = non-compliant or not this company. |
| 7 | FRESH ART CLUB LTD | small_exempt | freshartclub.com, **unconfirmed**: no CH no., no VAT on site | GB492114011, Endole (aggregator) only | 4 | CH no. in Endole URL matches sample. Number not published by the company itself. |
| 8 | SABAYAHAIR LTD | new | none found | none | 3 | New company, no web presence. |
| 9 | INGR TECHNOLOGY LTD | small | ingr.tech, **confirmed** (CH no. on /terms matches) | none, not on terms page | 3 | Strongest kind of "not found": right page, confirmed site. Not registered, or B2B firm not obliged to publish? |
| 10 | BLUE JAY OF LONDON LTD. | small | none found | none | 3 | Gemini offered VAT numbers of **similarly named** companies (BluJay Solutions, Bluejay Homes) → false-positive trap for name matching. |

In all 3 own-website finds, the VAT number and the matching CH number appear on the same site.
All 5 candidates pass the mod-97 checksum. HMRC verification so far: #4 only.

## Summary

| Outcome | Companies |
|---------|-----------|
| VAT candidate found | 5/10 (#1, #2, #3, #4, #7) |
| – from the company's own website | 3 (#1, #2, #3) |
| – from aggregators only | 2 (#4, #7) |
| Website found | 6/10 (#1, #2, #3, #6, #7, #9) |
| – confirmed by CH number on site | 4 (#1, #2, #3, #9) |
| Nothing found | 4/10 (#5, #6, #8, #10) |

n = 10: these are signals, not rates.

## What I learned

1. **Discovery is three sub-problems, not one.** (a) company → website is the hard
   part, CH has no website field. (b) website → VAT number is easy *when the number
   is there*: footer or T&Cs. (c) aggregators sit outside both.
2. **Aggregators hold numbers companies don't publish.** Chubb (#4) and Fresh Art
   Club (#7) don't show a VAT number on their own sites, yet vat-lookup.co.uk and
   Endole have one. #4 is verified correct at HMRC. Open question: where do they get
   them? Invoices and public documents, or systematic enumeration of the HMRC checker?
3. **Name matching is dangerous.** For #10 a search assistant returned valid-looking
   VAT numbers of *other* companies with similar names. Accepting "closest match"
   would silently attach a wrong number.
4. **The CH number is the identity anchor.** UK company websites must show the
   company's registered number. A VAT number on the same page as the correct CH
   number is strong evidence; a name match alone is not.
5. **Small and new companies often lack the legal disclosures** (#6, #7) → their
   websites can't be confirmed, even when found.
6. **Holding companies escape the SIC filter** (#5): they declare the group's
   operating SIC. Name patterns (Topco / Midco / Bidco / Holdings) are a better signal.
7. **LLM answers are not a source.** Gemini was right for #4, but n=1 proves nothing,
   and it was wrong-company for #10. Only a page I can cite counts.
8. **Manual search doesn't scale:** ~2.5 min/company → 500 companies ≈ 21h;
   3.58M ≈ 150k hours.