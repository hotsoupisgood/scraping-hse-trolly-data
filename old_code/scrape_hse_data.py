#!/usr/bin/env python3
"""
Script to scrape HSE TrolleyGAR data into a pandas DataFrame
Supports daily updates and appending to existing data
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import sqlite3

def scrape_hse_trolleygar(date_str=None):
    """
    Scrape HSE TrolleyGAR data for a specific date

    Args:
        date_str: Date in format 'DD/MM/YYYY'. If None, uses current date.

    Returns:
        pandas.DataFrame: Scraped data
    """
    # Set up the URL
    if date_str is None:
        date_str = datetime.now().strftime('%d/%m/%Y')

    # URL encode the date
    encoded_date = date_str.replace('/', '%2F')
    url = f'https://uec.hse.ie/uec/TGAR.php?EDDATE={encoded_date}'

    print(f"Fetching data for date: {date_str}")
    print(f"URL: {url}\n")

    # Fetch the page
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')

    # Find the main table
    table = soup.find('table')

    if not table:
        print("No table found on the page!")
        return None

    # Custom parser to handle the unusual multi-column layout
    # The table has a weird structure: the first data row contains ALL hospitals
    # horizontally, and subsequent rows repeat this data. We only need the first row.
    data = []

    # Skip header rows (first 2 rows) and get third row (index 2) which has all data
    rows = table.find_all('tr')

    # Find the first row with many hospital entries (50+ cells with colspan >= 8)
    data_row = None
    for row in rows[2:]:
        cells = row.find_all(['td', 'th'])
        hospital_count = sum(1 for c in cells if int(c.get('colspan', 1)) >= 8)

        if hospital_count >= 50:  # This is the master row with all hospitals
            data_row = row
            break

    if not data_row:
        print("Could not find master data row!")
        return None

    cells = data_row.find_all(['td', 'th'])

    # Parse cells - look for cells with colspan >= 8 which indicate hospital names
    i = 0
    while i < len(cells):
        cell = cells[i]
        colspan = int(cell.get('colspan', 1))

        # Found a hospital/entity name (has large colspan)
        if colspan >= 8:
            hospital_name = cell.get_text(strip=True)

            # Check if this is a regional header (section divider, not a hospital)
            # Regional headers like "HSE West & North West" don't have stat cells after them
            is_regional_header = (
                hospital_name.startswith('HSE ') and
                not hospital_name.endswith('Total') and
                not hospital_name.endswith('Hospital')
            )

            if is_regional_header:
                # Skip regional header - just move to next cell
                i += 1
                # Skip empty separator if present
                if i < len(cells) and cells[i].get_text(strip=True) == '':
                    i += 1
                continue

            # Not a regional header, so process as hospital/total
            i += 1

            # Skip the following empty cell (separator)
            if i < len(cells) and cells[i].get_text(strip=True) == '':
                i += 1

            # Extract next 11 data cells (but we only use some of them)
            # Pattern: ED_Trolleys, Ward_Trolleys, Total, empty, Surge, empty, Delayed, empty, >24hrs, empty, >75+
            stats = []
            for _ in range(11):
                if i < len(cells):
                    val = cells[i].get_text(strip=True)
                    stats.append(val if val else None)
                    i += 1
                else:
                    break

            # Only add if we have enough stats and valid name
            if hospital_name and len(stats) >= 11 and hospital_name != '':
                data.append([
                    hospital_name,
                    stats[0],  # ED Trolleys
                    stats[1],  # Ward Trolleys
                    stats[2],  # Total
                    stats[4],  # Surge Capacity
                    stats[6],  # Delayed Transfers
                    stats[8],  # Total Waiting >24hrs
                    stats[10]  # >75+yrs Waiting >24hrs
                ])
        else:
            # Not a hospital name cell, skip it
            i += 1

    # Create DataFrame
    df = pd.DataFrame(data, columns=[
        'Hospital',
        'ED_Trolleys',
        'Ward_Trolleys',
        'Total_Trolleys',
        'Surge_Capacity_in_Use',
        'Delayed_Transfers_of_Care',
        'Total_Waiting_gt_24hrs',
        'Age_75plus_Waiting_gt_24hrs'
    ])

    # Add metadata
    df['scrape_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    df['report_date'] = date_str

    print(f"Parsed {len(df)} hospital records\n")

    return df


def save_to_csv(df, filename=None, append=False):
    """
    Save DataFrame to CSV file

    Args:
        df: DataFrame to save
        filename: Output filename. If None, generates timestamped filename
        append: If True, appends to existing file (if it exists)
    """
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'hse_trolleygar_{timestamp}.csv'

    file_path = Path(filename)

    if append and file_path.exists():
        # Read existing data
        existing_df = pd.read_csv(filename)

        # Combine and remove duplicates based on all columns
        combined_df = pd.concat([existing_df, df], ignore_index=True)
        combined_df = combined_df.drop_duplicates()

        combined_df.to_csv(filename, index=False)
        print(f"Data appended to: {filename}")
        print(f"  Previous rows: {len(existing_df)}")
        print(f"  New rows: {len(df)}")
        print(f"  Total rows: {len(combined_df)}")
    else:
        df.to_csv(filename, index=False)
        print(f"Data saved to: {filename}")

    return filename


def scrape_date_range(start_date, end_date, db_name='hse_trolleygar.db'):
    """
    Scrape data for a range of dates and save to SQLite

    Args:
        start_date: Start date as string 'DD/MM/YYYY'
        end_date: End date as string 'DD/MM/YYYY'
        db_name: Output SQLite database filename

    Returns:
        pandas.DataFrame: Combined data
    """
    start = datetime.strptime(start_date, '%d/%m/%Y')
    end = datetime.strptime(end_date, '%d/%m/%Y')

    all_dfs = []
    current = start

    while current <= end:
        date_str = current.strftime('%d/%m/%Y')
        try:
            df = scrape_hse_trolleygar(date_str)
            if df is not None:
                all_dfs.append(df)
            current += timedelta(days=1)
        except Exception as e:
            print(f"Error scraping {date_str}: {e}")
            current += timedelta(days=1)
            continue

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        save_to_sqlite(combined_df, db_name)
        return combined_df
    return None


def save_to_sqlite(df, db_name='hse_trolleygar.db', table_name='trolleygar_data'):
    """
    Save DataFrame to SQLite database

    Args:
        df: DataFrame to save
        db_name: SQLite database filename
        table_name: Table name in database

    Returns:
        int: Number of rows inserted
    """
    conn = sqlite3.connect(db_name)

    try:
        # Check if table exists
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # Get existing row count
            existing_count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table_name}", conn).iloc[0]['count']
            print(f"Existing rows in database: {existing_count}")
        else:
            existing_count = 0
            print(f"Creating new table: {table_name}")

        # Append to database (if_exists='append' will create table if not exists)
        df.to_sql(table_name, conn, if_exists='append', index=False)

        # Get new count
        new_count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table_name}", conn).iloc[0]['count']
        rows_added = new_count - existing_count

        print(f"Data saved to SQLite database: {db_name}")
        print(f"  Table: {table_name}")
        print(f"  Rows added: {rows_added}")
        print(f"  Total rows: {new_count}")

        conn.commit()
        return rows_added

    finally:
        conn.close()


def remove_duplicates_from_db(db_name='hse_trolleygar.db', table_name='trolleygar_data'):
    """
    Remove duplicate rows from SQLite database

    Args:
        db_name: SQLite database filename
        table_name: Table name in database
    """
    conn = sqlite3.connect(db_name)

    try:
        # Get count before
        before_count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table_name}", conn).iloc[0]['count']

        # Create temporary table with unique rows
        cursor = conn.cursor()
        cursor.execute(f"""
            CREATE TABLE {table_name}_temp AS
            SELECT DISTINCT * FROM {table_name}
        """)

        # Drop original table
        cursor.execute(f"DROP TABLE {table_name}")

        # Rename temp table
        cursor.execute(f"ALTER TABLE {table_name}_temp RENAME TO {table_name}")

        # Get count after
        after_count = pd.read_sql(f"SELECT COUNT(*) as count FROM {table_name}", conn).iloc[0]['count']
        removed = before_count - after_count

        print(f"Duplicates removed: {removed}")
        print(f"Rows remaining: {after_count}")

        conn.commit()

    finally:
        conn.close()


def update_daily(filename='hse_trolleygar_data.csv', use_sqlite=True, db_name='hse_trolleygar.db'):
    """
    Fetch today's data and append to existing file/database

    Args:
        filename: CSV file to append to (if use_sqlite=False)
        use_sqlite: If True, saves to SQLite database instead of CSV
        db_name: SQLite database filename

    Returns:
        pandas.DataFrame: Today's data
    """
    today = datetime.now().strftime('%d/%m/%Y')
    print(f"Fetching today's data ({today})...")

    df = scrape_hse_trolleygar(today)

    if df is not None:
        if use_sqlite:
            save_to_sqlite(df, db_name)
        else:
            save_to_csv(df, filename, append=True)

    return df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Scrape HSE TrolleyGAR data')
    parser.add_argument('--mode', choices=['daily', 'date', 'range'], default='daily',
                        help='Scraping mode: daily (default), specific date, or date range')
    parser.add_argument('--date', help='Specific date to scrape (DD/MM/YYYY)')
    parser.add_argument('--start-date', help='Start date for range (DD/MM/YYYY)')
    parser.add_argument('--end-date', help='End date for range (DD/MM/YYYY)')
    parser.add_argument('--output', default='hse_trolleygar.db',
                        help='Output database file (default: hse_trolleygar.db)')
    parser.add_argument('--csv', action='store_true',
                        help='Use CSV instead of SQLite')
    parser.add_argument('--clean-duplicates', action='store_true',
                        help='Remove duplicates from database after scraping')

    args = parser.parse_args()

    try:
        if args.mode == 'daily':
            # Daily update mode
            print("="*60)
            print("DAILY UPDATE MODE")
            print("="*60 + "\n")

            df = update_daily(
                filename=args.output if args.csv else 'hse_trolleygar_data.csv',
                use_sqlite=not args.csv,
                db_name=args.output if not args.csv else 'hse_trolleygar.db'
            )

        elif args.mode == 'date':
            # Specific date mode
            if not args.date:
                print("Error: --date required for date mode")
                exit(1)

            print("="*60)
            print(f"SCRAPING DATA FOR {args.date}")
            print("="*60 + "\n")

            df = scrape_hse_trolleygar(args.date)

            if df is not None:
                if args.csv:
                    save_to_csv(df, args.output, append=True)
                else:
                    save_to_sqlite(df, args.output)

        elif args.mode == 'range':
            # Date range mode
            if not args.start_date or not args.end_date:
                print("Error: --start-date and --end-date required for range mode")
                exit(1)

            print("="*60)
            print(f"SCRAPING DATE RANGE: {args.start_date} to {args.end_date}")
            print("="*60 + "\n")

            df = scrape_date_range(args.start_date, args.end_date, args.output)

        # Clean duplicates if requested
        if args.clean_duplicates and not args.csv:
            print("\n" + "="*60)
            print("REMOVING DUPLICATES")
            print("="*60)
            remove_duplicates_from_db(args.output)

        # Display preview
        if 'df' in locals() and df is not None:
            print("\n" + "="*60)
            print("DATA PREVIEW")
            print("="*60)
            print(f"\nShape: {df.shape}")
            print(f"\nColumns: {list(df.columns)}")
            print(f"\nFirst few rows:")
            print(df.head())

            print("\n" + "="*60)
            print("SUCCESS!")
            print("="*60)

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
