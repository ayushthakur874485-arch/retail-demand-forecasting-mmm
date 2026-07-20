"""
Phase 3 - Marketing Mix Model
Log-log regression: log(sales) ~ log(tv_spend) + log(digital_spend) +
log(instore_promo_spend) + holiday flags + trend
Coefficients on log-log spend terms are directly interpretable as elasticities:
"a 1% increase in channel spend drives X% change in sales."
"""
import sqlite3
import pandas as pd
import numpy as np
import statsmodels.api as sm
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "rossmann.db")
OUT_DIR = os.path.join(BASE, "outputs")

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM agg_weekly_company_with_spend ORDER BY year, week_num", conn)
conn.close()

df = df.copy()
df["trend"] = np.arange(len(df))
df["log_sales"] = np.log(df["total_sales"])
df["log_tv"] = np.log(df["tv_spend"])
df["log_digital"] = np.log(df["digital_spend"])
df["log_instore"] = np.log(df["instore_promo_spend"])

X = df[["log_tv", "log_digital", "log_instore",
        "had_state_holiday", "had_school_holiday", "trend"]]
X = sm.add_constant(X)
y = df["log_sales"]

model = sm.OLS(y, X).fit()
print(model.summary())

# ---------- Elasticities ----------
elasticities = model.params[["log_tv", "log_digital", "log_instore"]]
pvalues = model.pvalues[["log_tv", "log_digital", "log_instore"]]

print("\n=== Channel elasticities (% sales lift per 1% spend increase) ===")
for ch, val in elasticities.items():
    sig = "significant (p<0.05)" if pvalues[ch] < 0.05 else "not significant"
    print(f"{ch:15s}: {val:+.4f}  -> a 10% spend increase moves sales by {val*10:+.2f}%  [{sig}]")

# ---------- Contribution decomposition (approx, for waterfall chart) ----------
baseline_log_sales = model.params["const"] + model.params["trend"] * df["trend"]
df["baseline_sales"] = np.exp(baseline_log_sales)
df["fitted_sales"] = np.exp(model.predict(X))
df["residual_contribution"] = df["fitted_sales"] - df["baseline_sales"]

os.makedirs(OUT_DIR, exist_ok=True)
mmm_out = df[["year", "week_num", "week_start", "total_sales", "fitted_sales",
              "baseline_sales", "tv_spend", "digital_spend", "instore_promo_spend"]]
mmm_out.to_csv(os.path.join(OUT_DIR, "mmm_results.csv"), index=False)

elast_out = pd.DataFrame({
    "channel": ["TV", "Digital", "In-store Promo"],
    "elasticity": elasticities.values,
    "p_value": pvalues.values,
    "sales_lift_pct_per_10pct_spend": elasticities.values * 10,
})
elast_out.to_csv(os.path.join(OUT_DIR, "mmm_elasticities.csv"), index=False)

print(f"\nModel R-squared: {model.rsquared:.3f}")
print(f"Saved: {os.path.join(OUT_DIR, 'mmm_results.csv')}")
print(f"Saved: {os.path.join(OUT_DIR, 'mmm_elasticities.csv')}")
