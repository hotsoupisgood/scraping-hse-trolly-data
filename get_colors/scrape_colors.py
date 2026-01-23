#!/usr/bin/env python3
"""
Scrape HSE TrolleyGAR data WITH color codes to determine thresholds.
The goal is to find the numerical boundaries for green/amber/red by
identifying cases where a 1-unit difference changes the color.
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import time


def extract_color(cell):
    """Extract color from cell's CSS class"""
    classes = cell.get('class', [])
    if isinstance(classes, str):
        classes = classes.split()

    for cls in classes:
        if 'green' in cls.lower():
            return 'green'
        elif 'red' in cls.lower():
            return 'red'
        elif 'orange' in cls.lower() or 'amber' in cls.lower() or 'yellow' in cls.lower():
            return 'amber'

    return 'none'


def scrape_with_colors(date_str):
    """
    Scrape HSE TrolleyGAR data including color codes for a specific date.

    Args:
        date_str: Date in format 'DD/MM/YYYY'

    Returns:
        pandas.DataFrame with hospital, values, and colors
    """
    encoded_date = date_str.replace('/', '%2F')
    url = f'https://uec.hse.ie/uec/TGAR.php?EDDATE={encoded_date}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')

    if not table:
        print(f"No table found for {date_str}")
        return None

    data = []
    rows = table.find_all('tr')

    # Find rows that contain hospital data
    # Each hospital row has a name cell with colspan and then data cells
    for row in rows:
        cells = row.find_all(['td', 'th'])

        # Skip rows without enough cells
        if len(cells) < 5:
            continue

        # Look for hospital name - usually first cell with colspan >= 8
        first_cell = cells[0]
        colspan = int(first_cell.get('colspan', 1))

        if colspan >= 8:
            hospital_name = first_cell.get_text(strip=True)

            # Skip regional headers (HSE XXX but not Total or Hospital)
            if hospital_name.startswith('HSE ') and 'Total' not in hospital_name:
                continue

            # Skip if empty name
            if not hospital_name:
                continue

            # Find the data cells - iterate through remaining cells
            # Structure: Name (colspan), then pairs of (value, separator)
            # Total column is typically the 3rd value and has color

            data_cells = []
            for cell in cells[1:]:
                cell_text = cell.get_text(strip=True)
                cell_color = extract_color(cell)
                cell_colspan = int(cell.get('colspan', 1))

                # Skip separator/spacer cells (usually width=10 or empty with no color)
                if cell_colspan == 1 and cell.get('width') in ['10', '50', '30']:
                    data_cells.append({
                        'value': cell_text,
                        'color': cell_color,
                        'width': cell.get('width')
                    })

            # Extract the key metrics with colors
            # Based on HTML structure: ED, Ward, Total (colored), Surge, Delayed, >24hrs, >75+
            if len(data_cells) >= 3:
                # Find the Total cell - it's usually the one with color that's not 'none'
                # and comes after ED and Ward trolleys
                record = {
                    'date': date_str,
                    'hospital': hospital_name,
                }

                # Try to extract values
                # Cells alternate: value, separator, value, separator...
                values = [c for c in data_cells if c['value'] and c['value'] != '']

                if len(values) >= 3:
                    record['ed_trolleys'] = values[0]['value'] if len(values) > 0 else None
                    record['ward_trolleys'] = values[1]['value'] if len(values) > 1 else None
                    record['total_trolleys'] = values[2]['value'] if len(values) > 2 else None
                    record['total_color'] = values[2]['color'] if len(values) > 2 else 'none'

                    # Also capture surge and delayed transfer colors if present
                    if len(values) > 3:
                        record['surge'] = values[3]['value']
                        record['surge_color'] = values[3]['color']
                    if len(values) > 4:
                        record['delayed'] = values[4]['value']
                        record['delayed_color'] = values[4]['color']

                    data.append(record)

    if not data:
        print(f"No hospital data extracted for {date_str}")
        return None

    df = pd.DataFrame(data)
    print(f"Scraped {len(df)} records for {date_str}")
    return df


def scrape_with_colors_v2(date_str):
    """
    Alternative approach: parse the entire table more carefully.
    This version handles the complex nested structure better.
    """
    encoded_date = date_str.replace('/', '%2F')
    url = f'https://uec.hse.ie/uec/TGAR.php?EDDATE={encoded_date}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table')

    if not table:
        print(f"No table found for {date_str}")
        return None

    data = []

    # Find all cells in the table
    all_cells = table.find_all(['td', 'th'])

    i = 0
    while i < len(all_cells):
        cell = all_cells[i]
        colspan = int(cell.get('colspan', 1))
        text = cell.get_text(strip=True)

        # Hospital/region name cells have large colspan (>=8)
        if colspan >= 8 and text:
            # Check if this is a regional header (skip) or hospital/total
            is_regional_header = (
                text.startswith('HSE ') and
                'Total' not in text and
                not text.endswith('Hospital')
            )

            if is_regional_header:
                i += 1
                continue

            hospital_name = text
            i += 1

            # Skip empty separator cell if present
            if i < len(all_cells) and all_cells[i].get_text(strip=True) == '':
                i += 1

            # Now collect the next 11 cells (or so) which are the data values
            # Pattern: ED, Ward, Total, spacer, Surge, spacer, Delayed, spacer, >24hrs, spacer, >75+
            stats = []
            for _ in range(12):
                if i < len(all_cells):
                    stat_cell = all_cells[i]
                    val = stat_cell.get_text(strip=True)
                    color = extract_color(stat_cell)
                    stats.append({'value': val, 'color': color})
                    i += 1

            # Extract the meaningful values (skip spacers which are usually empty)
            # Indices: 0=ED, 1=Ward, 2=Total(colored), 3=spacer, 4=Surge, 5=spacer,
            #          6=Delayed(colored), 7=spacer, 8=>24hrs, 9=spacer, 10=>75+
            if len(stats) >= 11:
                record = {
                    'date': date_str,
                    'hospital': hospital_name,
                    'ed_trolleys': stats[0]['value'] if stats[0]['value'] else None,
                    'ward_trolleys': stats[1]['value'] if stats[1]['value'] else None,
                    'total_trolleys': stats[2]['value'] if stats[2]['value'] else None,
                    'total_color': stats[2]['color'],
                    'surge': stats[4]['value'] if stats[4]['value'] else None,
                    'delayed': stats[6]['value'] if stats[6]['value'] else None,
                    'delayed_color': stats[6]['color'],
                    'gt_24hrs': stats[8]['value'] if stats[8]['value'] else None,
                    'gt_75_24hrs': stats[10]['value'] if stats[10]['value'] else None,
                }
                data.append(record)
        else:
            i += 1

    if not data:
        print(f"No hospital data extracted for {date_str}")
        return None

    df = pd.DataFrame(data)
    print(f"Scraped {len(df)} records for {date_str}")
    return df


def scrape_date_range(start_date, end_date, delay=1.0):
    """
    Scrape data for a range of dates.

    Args:
        start_date: Start date 'DD/MM/YYYY'
        end_date: End date 'DD/MM/YYYY'
        delay: Seconds to wait between requests

    Returns:
        Combined DataFrame
    """
    start = datetime.strptime(start_date, '%d/%m/%Y')
    end = datetime.strptime(end_date, '%d/%m/%Y')

    all_data = []
    current = start

    while current <= end:
        date_str = current.strftime('%d/%m/%Y')
        try:
            df = scrape_with_colors_v2(date_str)
            if df is not None:
                all_data.append(df)
        except Exception as e:
            print(f"Error scraping {date_str}: {e}")

        current += timedelta(days=1)
        time.sleep(delay)

    if all_data:
        return pd.concat(all_data, ignore_index=True)
    return None


def find_color_boundaries(df):
    """
    Analyze the data to find color boundaries.

    Look for cases where:
    - Same hospital on different days has different colors
    - The numerical difference is small (ideally 1 unit)

    This helps identify the exact threshold values.
    """
    # Convert to numeric
    df['total_trolleys_num'] = pd.to_numeric(df['total_trolleys'], errors='coerce')

    boundaries = []

    for hospital in df['hospital'].unique():
        hospital_data = df[df['hospital'] == hospital].copy()
        hospital_data = hospital_data.dropna(subset=['total_trolleys_num'])
        hospital_data = hospital_data.sort_values('total_trolleys_num')

        # Find color transitions
        prev_row = None
        for _, row in hospital_data.iterrows():
            if prev_row is not None:
                if prev_row['total_color'] != row['total_color']:
                    diff = row['total_trolleys_num'] - prev_row['total_trolleys_num']
                    boundaries.append({
                        'hospital': hospital,
                        'from_value': prev_row['total_trolleys_num'],
                        'from_color': prev_row['total_color'],
                        'to_value': row['total_trolleys_num'],
                        'to_color': row['total_color'],
                        'difference': diff,
                        'from_date': prev_row['date'],
                        'to_date': row['date']
                    })
            prev_row = row

    return pd.DataFrame(boundaries)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Scrape HSE TrolleyGAR colors')
    parser.add_argument('--date', help='Single date DD/MM/YYYY')
    parser.add_argument('--start', help='Start date DD/MM/YYYY')
    parser.add_argument('--end', help='End date DD/MM/YYYY')
    parser.add_argument('--output', default='colors_data.csv', help='Output CSV file')
    parser.add_argument('--analyze', action='store_true', help='Run boundary analysis')

    args = parser.parse_args()

    if args.date:
        df = scrape_with_colors_v2(args.date)
        if df is not None:
            print(f"\n{df.to_string()}")
            df.to_csv(args.output, index=False)
            print(f"\nSaved to {args.output}")

    elif args.start and args.end:
        df = scrape_date_range(args.start, args.end)
        if df is not None:
            df.to_csv(args.output, index=False)
            print(f"\nSaved {len(df)} records to {args.output}")

            if args.analyze:
                print("\n" + "="*60)
                print("COLOR BOUNDARY ANALYSIS")
                print("="*60)
                boundaries = find_color_boundaries(df)
                if not boundaries.empty:
                    # Sort by smallest difference to find the tightest boundaries
                    boundaries = boundaries.sort_values('difference')
                    print(boundaries.to_string())
                    boundaries.to_csv('boundaries.csv', index=False)
                    print("\nBoundaries saved to boundaries.csv")
                else:
                    print("No color transitions found in data")

    else:
        # Default: test with today
        today = datetime.now().strftime('%d/%m/%Y')
        df = scrape_with_colors_v2(today)
        if df is not None:
            print(f"\nSample data for {today}:")
            print(df[['hospital', 'total_trolleys', 'total_color']].head(20))
