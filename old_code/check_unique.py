#!/usr/bin/env python3
import sqlite3
import pandas as pd

conn = sqlite3.connect('hse_trolleygar.db')

df = pd.read_sql('SELECT * FROM trolleygar_data WHERE Hospital LIKE "%Total%" OR Hospital LIKE "%HSE%"', conn)

print(f"Total rows in DB: {pd.read_sql('SELECT COUNT(*) FROM trolleygar_data', conn).iloc[0,0]}")
print(f"\nRows with 'Total' or 'HSE' in name: {len(df)}")
print(df[['Hospital', 'ED_Trolleys', 'Ward_Trolleys', 'Total_Trolleys']].head(20))

conn.close()
