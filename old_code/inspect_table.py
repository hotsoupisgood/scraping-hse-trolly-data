#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

url = 'https://uec.hse.ie/uec/TGAR.php?EDDATE=07%2F11%2F2025'
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

table = soup.find('table')

# Print first 5 rows to understand structure
print("First 5 rows of the table:")
print("="*80)
for i, row in enumerate(table.find_all('tr')[:5]):
    print(f"\nRow {i}:")
    for j, cell in enumerate(row.find_all(['th', 'td'])):
        colspan = cell.get('colspan', '1')
        rowspan = cell.get('rowspan', '1')
        text = cell.get_text(strip=True)
        print(f"  Cell {j}: '{text}' (colspan={colspan}, rowspan={rowspan})")
