import pandas as pd
import numpy as np
import re
import json

def parse_date(val):
    if pd.isna(val):
        return '2026-06-01'
    val_str = str(val).strip()
    # Format 1: 2026/6/15 or 2026-06-15
    if '/' in val_str or '-' in val_str:
        val_str = val_str.replace('/', '-')
        parts = val_str.split('-')
        if len(parts) == 3:
            y, m, d = parts
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    # Format 2: 6月15日
    m_match = re.search(r'(\d+)月(\d+)日', val_str)
    if m_match:
        m, d = m_match.groups()
        return f"2026-{int(m):02d}-{int(d):02d}"
    # Format 3: 0615 (MMDD)
    if val_str.isdigit() and len(val_str) == 4:
        m = val_str[:2]
        d = val_str[2:]
        return f"2026-{int(m):02d}-{int(d):02d}"
    return '2026-06-01'

def clean_data():
    df = pd.read_csv('data/主檔.csv', encoding='utf-8-sig')
    
    # 1. Drop duplicates
    initial_count = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    duplicates_removed = initial_count - len(df)
    
    # 2. Parse dates
    df['標準日期'] = df['月份'].apply(parse_date)
    df['月份_排序'] = pd.to_datetime(df['標準日期']).dt.to_period('M').astype(str)
    
    # 3. Detect and fix decimal point misalignments (~100x outliers)
    # Check numeric columns: 金額, 數量, 比率, 耗時分鐘
    num_cols = ['金額', '數量', '比率', '耗時分鐘']
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        # If value is extremely high compared to median (> 50x median and > threshold), divide by 100
        median_val = df[col].median()
        # Find outliers that are roughly 100x
        outlier_mask = df[col] > (median_val * 30)
        if outlier_mask.sum() > 0:
            df.loc[outlier_mask, col] = df.loc[outlier_mask, col] / 100.0

    # 4. Handle missing values in 數量 (impute with median of 項目 or 單位)
    df['數量'] = df['數量'].fillna(df.groupby('項目')['數量'].transform('median'))
    df['數量'] = df['數量'].fillna(df['數量'].median())
    
    df['金額'] = df['金額'].fillna(df['金額'].median())
    df['耗時分鐘'] = df['耗時分鐘'].fillna(df['耗時分鐘'].median())
    df['比率'] = df['比率'].fillna(df['比率'].median())
    df['來源'] = df['來源'].fillna('未填寫')
    
    # 5. Calculate Unit Cost & Energy Consumption per unit output
    # Unit Cost (每台車架成本) = 金額 / 數量
    df['單位成本'] = df['金額'] / df['數量'].replace(0, 1)
    # Energy consumption per unit (單位產出能耗)
    df['單位能耗'] = df['耗時分鐘'] / df['數量'].replace(0, 1)
    
    # 6. Summary metrics
    monthly_summary = df.groupby('月份_排序').agg({
        '金額': 'sum',
        '數量': 'sum',
        '耗時分鐘': 'sum',
        '單位成本': 'mean',
        '單位能耗': 'mean'
    }).reset_index()
    
    # Identify anomalies (e.g. top 3 months or items with highest unit cost / energy consumption)
    top_cost_items = df.sort_values(by='單位成本', ascending=False).head(10).to_dict(orient='records')
    
    print(f"Cleaned records: {len(df)} (Duplicates removed: {duplicates_removed})")
    
    # Export cleaned data to JSON for frontend use
    output_data = {
        "records": df.to_dict(orient='records'),
        "monthly": monthly_summary.to_dict(orient='records'),
        "stats": {
            "total_records": len(df),
            "total_cost": float(df['金額'].sum()),
            "total_qty": float(df['數量'].sum()),
            "avg_unit_cost": float(df['單位成本'].mean())
        }
    }
    
    with open('cleaned_data.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

if __name__ == '__main__':
    clean_data()
