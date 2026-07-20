"""
Phase 1b - Synthetic marketing spend layer
Rossmann has no real ad-spend data (normal for this dataset), so we generate a
realistic weekly spend-by-channel table, correlated with real promo activity +
seasonality, with noise -- exactly how public MMM case studies are built when
real spend data isn't available. Written back into the same SQLite DB.
"""
import sqlite3
import pandas as pd
import numpy as np
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "rossmann.db")

np.random.seed(42)

conn = sqlite3.connect(DB_PATH)
weekly = pd.read_sql("SELECT * FROM agg_weekly_company ORDER BY year, week_num", conn)

n = len(weekly)
t = np.arange(n)

# Baseline spend per channel + response to real promo_intensity + mild growth trend + noise
tv_spend = 80000 + 40000 * weekly["promo_intensity"] + 300 * t + np.random.normal(0, 8000, n)
digital_spend = 30000 + 60000 * weekly["promo_intensity"] + 500 * t + np.random.normal(0, 6000, n)
instore_promo_spend = 20000 + 90000 * weekly["promo_intensity"] + np.random.normal(0, 5000, n)

# Clip to avoid negative spend weeks
weekly["tv_spend"] = np.clip(tv_spend, 5000, None).round(0)
weekly["digital_spend"] = np.clip(digital_spend, 5000, None).round(0)
weekly["instore_promo_spend"] = np.clip(instore_promo_spend, 2000, None).round(0)
weekly["total_marketing_spend"] = (
    weekly["tv_spend"] + weekly["digital_spend"] + weekly["instore_promo_spend"]
)

weekly.to_sql("agg_weekly_company_with_spend", conn, if_exists="replace", index=False)
conn.commit()
conn.close()

print(f"agg_weekly_company_with_spend written: {len(weekly)} rows")
print(weekly[["year", "week_num", "total_sales", "promo_intensity",
              "tv_spend", "digital_spend", "instore_promo_spend"]].head(8).to_string(index=False))
print("\nNOTE FOR YOUR PROJECT README / RESUME TALKING POINT:")
print("Marketing spend-by-channel is synthetically generated (no public real spend")
print("data exists for this dataset) but is correlated to real weekly promo activity")
print("+ trend + noise, so the MMM regression recovers realistic, defensible elasticities.")
print("Be upfront about this in interviews -- it's a standard, expected practice for")
print("portfolio MMM projects and shows you understand what MMM actually models.")
