"""
Run the SQL analysis and save results + charts to outputs/.

Default: loads the CSVs into a local SQLite database so it runs anywhere.
PostgreSQL: set DATABASE_URL (e.g. postgresql://user:pass@localhost:5432/retail)
after loading the data with sql/schema.sql.
"""
import os
import re
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).parent
DATA, SQL, OUT = ROOT / "data", ROOT / "sql", ROOT / "outputs"
OUT.mkdir(exist_ok=True)
TABLES = ["customers", "products", "orders", "order_items"]


def connect():
    url = os.getenv("DATABASE_URL")
    if url:
        import psycopg2
        return psycopg2.connect(url)
    conn = sqlite3.connect(ROOT / "retail.db")
    for t in TABLES:
        pd.read_csv(DATA / f"{t}.csv").to_sql(t, conn, if_exists="replace", index=False)
    return conn


def load_queries():
    text = (SQL / "analysis.sql").read_text()
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def main():
    conn = connect()
    results = {name: pd.read_sql_query(q, conn) for name, q in load_queries().items()}
    for name, df in results.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"\n== {name} ==\n{df.head(12).to_string(index=False)}")

    # Chart 1: seasonal revenue by fabric
    trend = results["monthly_fabric_trend"].pivot(index="order_month", columns="fabric", values="revenue")
    ax = trend.plot(figsize=(11, 5), linewidth=2)
    ax.set_title("Monthly revenue by fabric")
    ax.set_xlabel("Month"); ax.set_ylabel("Revenue ($)")
    plt.tight_layout(); plt.savefig(OUT / "seasonal_trends.png", dpi=150); plt.close()

    # Chart 2: revenue by seasonal collection
    share = results["collection_performance"].set_index("collection")["avg_monthly_revenue"].sort_values()
    ax = share.plot.barh(figsize=(8, 4), color="#4C72B0")
    ax.set_title("Average monthly revenue by seasonal collection"); ax.set_xlabel("Revenue ($)"); ax.set_ylabel("")
    plt.tight_layout(); plt.savefig(OUT / "collection_revenue.png", dpi=150); plt.close()

    # Chart 3: cohort retention
    ret = results["cohort_retention"]
    ax = ret.plot(x="cohort_month", y="retention_pct", figsize=(11, 4), legend=False, linewidth=2)
    ax.set_title("Retention by first-purchase cohort"); ax.set_xlabel("Cohort (first order month)"); ax.set_ylabel("% who ordered again")
    plt.tight_layout(); plt.savefig(OUT / "cohort_retention.png", dpi=150); plt.close()
    print(f"\nSaved results and charts to {OUT}/")


if __name__ == "__main__":
    main()
