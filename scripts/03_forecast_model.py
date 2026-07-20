"""
Phase 2 - Demand forecasting
Weekly company-level sales forecast using Prophet, with promo intensity and
holiday flags as external regressors. Train/test split evaluated with MAPE/RMSE.
"""
import sqlite3
import pandas as pd
import numpy as np
import os
from prophet import Prophet

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "rossmann.db")
OUT_DIR = os.path.join(BASE, "outputs")

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql("SELECT * FROM agg_weekly_company_with_spend ORDER BY year, week_num", conn)
conn.close()

df["week_start"] = pd.to_datetime(df["week_start"])
prophet_df = df.rename(columns={"week_start": "ds", "total_sales": "y"})[
    ["ds", "y", "promo_intensity", "had_state_holiday", "had_school_holiday"]
]

# Train/test split -- last 12 weeks held out for evaluation
n = len(prophet_df)
test_size = 12
train_df = prophet_df.iloc[: n - test_size].copy()
test_df = prophet_df.iloc[n - test_size :].copy()

model = Prophet(
    yearly_seasonality=True,
    weekly_seasonality=False,   # already weekly grain
    seasonality_mode="multiplicative",
)
model.add_regressor("promo_intensity")
model.add_regressor("had_state_holiday")
model.add_regressor("had_school_holiday")
model.fit(train_df)

future = prophet_df[["ds", "promo_intensity", "had_state_holiday", "had_school_holiday"]].copy()
forecast = model.predict(future)

result = prophet_df.merge(
    forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]], on="ds", how="left"
)
result["set"] = ["train"] * len(train_df) + ["test"] * len(test_df)

# ---------- Evaluate on test set ----------
test_eval = result[result["set"] == "test"]
mape = float(np.mean(np.abs((test_eval["y"] - test_eval["yhat"]) / test_eval["y"])) * 100)
rmse = float(np.sqrt(np.mean((test_eval["y"] - test_eval["yhat"]) ** 2)))

print(f"Test MAPE: {mape:.2f}%")
print(f"Test RMSE: {rmse:,.0f}")
print("\nLast 6 weeks -- actual vs forecast:")
print(test_eval[["ds", "y", "yhat"]].tail(6).to_string(index=False))

# ---------- Save forecast output for Power BI ----------
os.makedirs(OUT_DIR, exist_ok=True)
result_out = result.rename(columns={"ds": "week_start", "y": "actual_sales", "yhat": "forecast_sales"})
result_out.to_csv(os.path.join(OUT_DIR, "forecast_results.csv"), index=False)

with open(os.path.join(OUT_DIR, "forecast_metrics.txt"), "w") as f:
    f.write(f"Test MAPE: {mape:.2f}%\nTest RMSE: {rmse:,.0f}\nTest weeks: {test_size}\n")

print(f"\nSaved: {os.path.join(OUT_DIR, 'forecast_results.csv')}")
