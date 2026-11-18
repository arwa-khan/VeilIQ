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

    # ---------------- Colour intelligence charts ----------------
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    surface, ink, ink2, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
    style = {"figure.facecolor": surface, "axes.facecolor": surface, "savefig.facecolor": surface,
             "axes.edgecolor": grid, "text.color": ink, "axes.labelcolor": ink2,
             "xtick.color": ink2, "ytick.color": ink2, "axes.spines.top": False,
             "axes.spines.right": False, "axes.titleweight": "bold", "axes.titlelocation": "left"}

    with plt.rc_context(style):
        # Chart 4: seasonal colour demand index (diverging around 100 = normal)
        order = ["Winter", "Ramadan & Eid", "Spring", "Summer", "Back to School", "Fall"]
        idx = (results["colour_collection_index"]
               .pivot(index="colour", columns="collection", values="demand_index")[order])
        idx = idx.loc[idx["Ramadan & Eid"].sort_values(ascending=False).index]
        cmap = LinearSegmentedColormap.from_list("div", ["#c23a39", "#f0efec", "#1c5cab"])
        norm = TwoSlopeNorm(vmin=40, vcenter=100, vmax=170)
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.imshow(idx.values, cmap=cmap, norm=norm, aspect="auto")
        for i in range(idx.shape[0]):
            for j in range(idx.shape[1]):
                v = idx.values[i, j]
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=10,
                        color="white" if abs(v - 100) > 40 else ink)
        ax.set_xticks(range(len(order)), order)
        ax.set_yticks(range(len(idx)), idx.index)
        ax.tick_params(length=0)
        for side in ax.spines.values():
            side.set_visible(False)
        ax.set_title("Colour demand by collection (100 = normal; blue = sells more, red = sells less)",
                     fontsize=11)
        plt.tight_layout(); plt.savefig(OUT / "colour_season_index.png", dpi=200); plt.close()

        # Chart 5: return rate by colour, top 3 highlighted
        rr = results["colour_return_rate"].sort_values("return_rate_pct")
        top3 = set(rr.nlargest(3, "return_rate_pct")["colour"])
        fig, ax = plt.subplots(figsize=(7.5, 4.2))
        bars = ax.barh(rr["colour"], rr["return_rate_pct"], height=0.6, edgecolor=surface, linewidth=2,
                       color=["#2a78d6" if c in top3 else "#c9c8c2" for c in rr["colour"]])
        for b, v in zip(bars, rr["return_rate_pct"]):
            ax.text(v + 0.2, b.get_y() + b.get_height() / 2, f"{v:.1f}%", va="center", fontsize=10)
        ax.set_xlabel("Return rate (% of units sold)")
        ax.xaxis.grid(True, color=grid); ax.set_axisbelow(True)
        ax.set_title("Navy, Ivory and Sage are returned the most")
        plt.tight_layout(); plt.savefig(OUT / "colour_return_rate.png", dpi=200); plt.close()

        # Chart 6: discounting in season vs off season
        ds = results["colour_off_season_discounting"].set_index("season_fit")
        fig, ax = plt.subplots(figsize=(6, 3.8))
        bars = ax.bar(ds.index, ds["pct_units_discounted"], width=0.5, edgecolor=surface, linewidth=2,
                      color=["#2a78d6", "#eb6834"])
        for b, v in zip(bars, ds["pct_units_discounted"]):
            ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.0f}%", ha="center", fontsize=11)
        ax.set_ylim(0, 75); ax.set_ylabel("% of units sold on discount")
        ax.yaxis.grid(True, color=grid); ax.set_axisbelow(True)
        ax.set_title("Off-season colours need discounts to sell")
        plt.tight_layout(); plt.savefig(OUT / "colour_off_season_discounting.png", dpi=200); plt.close()
    print(f"\nSaved results and charts to {OUT}/")


if __name__ == "__main__":
    main()
