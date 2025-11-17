#!/usr/bin/env python3
import sqlite3
import pandas as pd

# Connect to the database
conn = sqlite3.connect('hse_trolleygar.db')

# Read the data
df = pd.read_sql('SELECT * FROM trolleygar_data LIMIT 10', conn)

# Display columns
print("Columns:")
for i, col in enumerate(df.columns):
    print(f"{i}: {col}")

print("\n" + "="*80)
print("First 10 rows:")
print("="*80)

# Display the data transposed for better readability
print(df.head(10).T)

conn.close()
