#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

url = 'https://uec.hse.ie/uec/TGAR.php?EDDATE=07%2F11%2F2025'
response = requests.get(url)
soup = BeautifulSoup(response.content, 'html.parser')

table = soup.find('table')
rows = table.find_all('tr')[2:]  # Skip header rows

print(f"Total rows (excluding headers): {len(rows)}\n")

# Count how many hospitals appear in each row
for row_num, row in enumerate(rows[:10]):  # First 10 rows
    cells = row.find_all(['td', 'th'])

    if len(cells) == 1:
        print(f"Row {row_num}: REGION HEADER - {cells[0].get_text(strip=True)}")
        continue

    # Count cells with colspan >= 8
    hospital_cells = [c for c in cells if int(c.get('colspan', 1)) >= 8]

    if hospital_cells:
        names = [c.get_text(strip=True) for c in hospital_cells]
        print(f"Row {row_num}: {len(hospital_cells)} entries - {names}")
    else:
        print(f"Row {row_num}: No hospital entries (blank row?)")
