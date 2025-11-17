#!/usr/bin/env python3
import sqlite3
import pandas as pd

conn = sqlite3.connect('hse_trolleygar.db')

df = pd.read_sql('''SELECT * FROM trolleygar_data
                    WHERE Hospital NOT LIKE "%Total%"
                    AND Hospital NOT LIKE "%HSE%"
                    AND Hospital IS NOT NULL
                    AND Hospital != ""
                    ORDER BY Hospital
                    LIMIT 30''', conn)

print(f"Sample hospital records:")
print(df[['Hospital', 'ED_Trolleys', 'Ward_Trolleys', 'Total_Trolleys']])

print(f"\n\nUnique hospitals: {df['Hospital'].nunique()}")

conn.close()
