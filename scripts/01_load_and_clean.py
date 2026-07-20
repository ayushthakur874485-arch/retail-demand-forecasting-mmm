"""
Phase 1 - SQL layer
Loads raw Rossmann CSVs into SQLite, builds cleaned + aggregated tables.
Run: python3 01_load_and_clean.py
"""
import sqlite3
import pandas as pd
import numpy as np
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "rossmann.db")
DATA_DIR = os.path.join(BASE, "data")

conn = sqlite3.connect(DB_PATH)

# ---------- 1. Load raw CSVs as-is (raw layer) ----------
sales = pd.read_csv(os.path.join(DATA_DIR, "train.csv"), low_memory=False)
store = pd.read_csv(os.path.join(DATA_DIR, "store.csv"))

sales.to_sql("raw_sales", conn, if_exists="replace", index=False)
store.to_sql("raw_store", conn, if_exists="replace", index=False)
print(f"raw_sales: {len(sales):,} rows | raw_store: {len(store):,} rows")

# ---------- 2. Staging: clean types, parse dates ----------
cur = conn.cursor()
cur.executescript("""
DROP TABLE IF EXISTS stg_sales;
CREATE TABLE stg_sales AS
SELECT
    Store,
    DATE(Date) AS sale_date,
    CAST(strftime('%Y', Date) AS INTEGER) AS year,
    CAST(strftime('%W', Date) AS INTEGER) AS week_num,
    DayOfWeek AS day_of_week,
    Sales AS sales,
    Customers AS customers,
    Open AS is_open,
    Promo AS is_promo,
    CASE WHEN StateHoliday IN ('a','b','c') THEN 1 ELSE 0 END AS is_state_holiday,
    SchoolHoliday AS is_school_holiday
FROM raw_sales
WHERE Open = 1 AND Sales > 0;   -- exclude closed-store / zero-sales noise

DROP TABLE IF EXISTS stg_store;
CREATE TABLE stg_store AS
SELECT
    Store,
    StoreType AS store_type,
    Assortment AS assortment,
    CompetitionDistance AS competition_distance,
    Promo2 AS has_promo2
FROM raw_store;
""")
conn.commit()

n = cur.execute("SELECT COUNT(*) FROM stg_sales").fetchone()[0]
print(f"stg_sales (open days, sales>0): {n:,} rows")

# ---------- 3. Cleaned fact table: sales joined with store attributes ----------
cur.executescript("""
DROP TABLE IF EXISTS fct_sales_daily;
CREATE TABLE fct_sales_daily AS
SELECT
    s.Store AS store_id,
    s.sale_date,
    s.year,
    s.week_num,
    s.day_of_week,
    s.sales,
    s.customers,
    s.is_promo,
    s.is_state_holiday,
    s.is_school_holiday,
    t.store_type,
    t.assortment,
    t.competition_distance
FROM stg_sales s
LEFT JOIN stg_store t ON s.Store = t.Store;
""")
conn.commit()
print("fct_sales_daily created")

# ---------- 4. Weekly aggregation (company-wide) — grain for forecasting + MMM ----------
cur.executescript("""
DROP TABLE IF EXISTS agg_weekly_company;
CREATE TABLE agg_weekly_company AS
SELECT
    year,
    week_num,
    MIN(sale_date) AS week_start,
    SUM(sales) AS total_sales,
    SUM(customers) AS total_customers,
    AVG(is_promo) AS promo_intensity,        -- fraction of stores running promo that week
    MAX(is_state_holiday) AS had_state_holiday,
    MAX(is_school_holiday) AS had_school_holiday,
    COUNT(DISTINCT store_id) AS active_stores
FROM fct_sales_daily
GROUP BY year, week_num
ORDER BY year, week_num;
""")
conn.commit()

n = cur.execute("SELECT COUNT(*) FROM agg_weekly_company").fetchone()[0]
print(f"agg_weekly_company: {n} weekly rows")

# ---------- 5. Weekly aggregation by store_type — for segmentation views ----------
cur.executescript("""
DROP TABLE IF EXISTS agg_weekly_storetype;
CREATE TABLE agg_weekly_storetype AS
SELECT
    year,
    week_num,
    store_type,
    SUM(sales) AS total_sales,
    AVG(is_promo) AS promo_intensity
FROM fct_sales_daily
GROUP BY year, week_num, store_type
ORDER BY year, week_num, store_type;
""")
conn.commit()
print("agg_weekly_storetype created")

conn.close()
print("\nDone. DB at:", DB_PATH)
