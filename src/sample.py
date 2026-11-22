"""Draw the stratified random sample from the Companies House snapshot.

Input : data/raw/ch.parquet         (made by explore_ch.py)
Output: data/sample/sample.csv       (500 companies, shuffled processing order)
        data/sample/strata_sizes.csv (population size per stratum, for reweighting)

Design decisions: see notes/log.md (18:15 and 18:20-18:32).
"""
import duckdb

SEED = "veridion-2026-11-22"   # fixed → same sample every run
PER_STRATUM = 94
CONTROL = 30

con = duckdb.connect()
# Low-memory settings for a laptop: spill to disk instead of crashing
con.sql("SET temp_directory = 'data/raw/duckdb_tmp'")
con.sql("SET preserve_insertion_order = false")
con.sql("CREATE VIEW ch AS SELECT * FROM 'data/raw/ch.parquet'")

# 1. Base population + helper columns
con.sql("""
CREATE TABLE pop AS
SELECT CompanyNumber, CompanyName,                 -- only the columns we need
       "RegAddress.AddressLine1" AS addr1, "RegAddress.AddressLine2" AS addr2,
       "RegAddress.PostTown" AS town, "RegAddress.PostCode" AS postcode,
       CompanyCategory, IncorporationDate, URI,
       "SICCode.SicText_1" AS sic1, "SICCode.SicText_2" AS sic2,
       "SICCode.SicText_3" AS sic3, "SICCode.SicText_4" AS sic4,
       "Accounts.AccountCategory" AS acc,
       right(IncorporationDate, 4) AS inc_year,
       -- 5-digit SIC codes actually supplied (drops NULL / 'None Supplied')
       list_filter(
         [left("SICCode.SicText_1", 5), left("SICCode.SicText_2", 5),
          left("SICCode.SicText_3", 5), left("SICCode.SicText_4", 5)],
         lambda x: x IS NOT NULL AND regexp_matches(x, '^[0-9]{5}$')
       ) AS sics
FROM ch
WHERE CompanyStatus = 'Active'
  AND CompanyCategory IN ('Private Limited Company',
                          'Public Limited Company',
                          'Limited Liability Partnership')
""")

# 2. Irrelevant = dormant, or EVERY supplied SIC is in the excluded list
#    (a company with 68100 + 47910 still trades, so it is kept)
con.sql("""
CREATE TABLE pop2 AS
SELECT *,
  acc = 'DORMANT'
  OR (len(sics) > 0 AND len(list_filter(sics,
        lambda x: NOT (x LIKE '68%' OR x IN ('64209', '98000', '99999')))) = 0)
  AS irrelevant
FROM pop
""")

con.sql("DROP TABLE pop")

# 3. Assign strata
con.sql("""
CREATE TABLE strat AS
SELECT *,
  CASE
    WHEN irrelevant THEN 'control'
    WHEN acc = 'NO ACCOUNTS FILED' AND inc_year IN ('2025', '2026') THEN 'new'
    WHEN acc = 'MICRO ENTITY' THEN 'micro'
    WHEN acc = 'TOTAL EXEMPTION FULL' THEN 'small_exempt'
    WHEN acc IN ('SMALL', 'UNAUDITED ABRIDGED', 'AUDITED ABRIDGED',
                 'TOTAL EXEMPTION SMALL') THEN 'small'
    WHEN acc IN ('FULL', 'MEDIUM', 'GROUP', 'AUDIT EXEMPTION SUBSIDIARY')
         THEN 'large'
    ELSE NULL   -- left out: see log
  END AS stratum
FROM pop2
""")

con.sql("DROP TABLE pop2")

# 4. Population size per stratum (needed to reweight results later)
con.sql("""
COPY (SELECT coalesce(stratum, 'left_out') AS stratum, count(*) AS population
      FROM strat GROUP BY 1 ORDER BY 2 DESC)
TO 'data/sample/strata_sizes.csv' (HEADER)
""")

# 5. Random draw per stratum (deterministic hash of company number + seed),
#    then a global shuffle for the processing order
con.sql(f"""
COPY (
  SELECT row_number() OVER (ORDER BY hash(CompanyNumber || '{SEED}-order'))
           AS process_order,
         stratum, CompanyNumber, CompanyName,
         addr1, addr2, town, postcode,
         CompanyCategory, acc AS account_category, IncorporationDate,
         sic1, sic2, sic3, sic4, URI
  FROM (
    SELECT *, row_number() OVER (PARTITION BY stratum
                                 ORDER BY hash(CompanyNumber || '{SEED}')) AS rn
    FROM strat WHERE stratum IS NOT NULL
  )
  WHERE (stratum <> 'control' AND rn <= {PER_STRATUM})
     OR (stratum = 'control' AND rn <= {CONTROL})
  ORDER BY process_order
) TO 'data/sample/sample.csv' (HEADER)
""")

print(con.sql("SELECT * FROM read_csv_auto('data/sample/strata_sizes.csv')"))
print(con.sql("""SELECT stratum, count(*) n FROM read_csv_auto('data/sample/sample.csv')
                 GROUP BY 1 ORDER BY 1"""))