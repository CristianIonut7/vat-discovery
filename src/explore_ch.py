"""Quick look at the Companies House bulk snapshot."""
import glob
import os
import duckdb

csv = glob.glob("data/raw/*.csv")[0]
parquet = "data/raw/ch.parquet"
con = duckdb.connect()

# One-time conversion: CSV (slow to re-read) -> Parquet (fast)
if not os.path.exists(parquet):
    print("Converting CSV to Parquet (one time, ~1-2 min)...")
    con.sql(f"""COPY (SELECT * FROM read_csv_auto('{csv}', all_varchar=true))
               TO '{parquet}' (FORMAT parquet)""")

con.sql(f"CREATE VIEW ch AS SELECT * FROM '{parquet}'")


def show(title, query):
    print(f"\n--- {title} ---")
    for row in con.sql(query).fetchall():
        print(row)


show("Total rows", "SELECT count(*) FROM ch")
show("CompanyStatus", """SELECT CompanyStatus, count(*) n FROM ch
                         GROUP BY 1 ORDER BY n DESC""")
show("CompanyCategory (active only)", """SELECT CompanyCategory, count(*) n FROM ch
     WHERE CompanyStatus = 'Active' GROUP BY 1 ORDER BY n DESC""")
show("AccountCategory (active only)", """SELECT "Accounts.AccountCategory", count(*) n
     FROM ch WHERE CompanyStatus = 'Active' GROUP BY 1 ORDER BY n DESC""")
show("Top 15 SIC codes (active only)", """SELECT "SICCode.SicText_1", count(*) n
     FROM ch WHERE CompanyStatus = 'Active' GROUP BY 1 ORDER BY n DESC LIMIT 15""")
show("Incorporation year (active, last 15 yrs)", """
     SELECT right(IncorporationDate, 4) yr, count(*) n FROM ch
     WHERE CompanyStatus = 'Active' GROUP BY 1 ORDER BY yr DESC LIMIT 15""")
show("NO ACCOUNTS FILED by incorporation year (active)", """
     SELECT right(IncorporationDate, 4) yr, count(*) n FROM ch
     WHERE CompanyStatus = 'Active'
       AND "Accounts.AccountCategory" = 'NO ACCOUNTS FILED'
     GROUP BY 1 ORDER BY yr DESC LIMIT 6""")