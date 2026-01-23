#!/usr/bin/env python3
"""
Analyze scraped color data to determine hospital-specific thresholds.
"""

import pandas as pd
import numpy as np


def analyze_hospital_thresholds(csv_path):
    """
    Analyze color data to determine thresholds for each hospital.

    Returns a DataFrame with inferred thresholds.
    """
    df = pd.read_csv(csv_path)

    # Convert to numeric
    df['total_num'] = pd.to_numeric(df['total_trolleys'], errors='coerce')

    results = []

    for hospital in sorted(df['hospital'].unique()):
        if hospital == 'National Total':
            continue

        hosp_data = df[df['hospital'] == hospital].copy()
        hosp_data = hosp_data.dropna(subset=['total_num'])

        if len(hosp_data) == 0:
            continue

        # Get value ranges by color
        green_vals = hosp_data[hosp_data['total_color'] == 'green']['total_num']
        amber_vals = hosp_data[hosp_data['total_color'] == 'amber']['total_num']
        red_vals = hosp_data[hosp_data['total_color'] == 'red']['total_num']

        result = {
            'hospital': hospital,
            'green_max': green_vals.max() if len(green_vals) > 0 else None,
            'green_min': green_vals.min() if len(green_vals) > 0 else None,
            'green_count': len(green_vals),
            'amber_max': amber_vals.max() if len(amber_vals) > 0 else None,
            'amber_min': amber_vals.min() if len(amber_vals) > 0 else None,
            'amber_count': len(amber_vals),
            'red_min': red_vals.min() if len(red_vals) > 0 else None,
            'red_max': red_vals.max() if len(red_vals) > 0 else None,
            'red_count': len(red_vals),
        }

        # Infer thresholds
        # Green → Amber threshold: highest green + 1 (or lowest amber)
        if result['green_max'] is not None and result['amber_min'] is not None:
            result['amber_threshold'] = min(result['green_max'] + 1, result['amber_min'])
        elif result['amber_min'] is not None:
            result['amber_threshold'] = result['amber_min']
        else:
            result['amber_threshold'] = None

        # Amber → Red threshold: highest amber + 1 (or lowest red)
        if result['amber_max'] is not None and result['red_min'] is not None:
            result['red_threshold'] = min(result['amber_max'] + 1, result['red_min'])
        elif result['green_max'] is not None and result['red_min'] is not None:
            # No amber observed - threshold might be right after green
            result['red_threshold'] = result['red_min']
        elif result['red_min'] is not None:
            result['red_threshold'] = result['red_min']
        else:
            result['red_threshold'] = None

        results.append(result)

    return pd.DataFrame(results)


def find_exact_boundaries(csv_path):
    """
    Find instances where we have exact proof of boundaries
    (1-unit color changes).
    """
    df = pd.read_csv(csv_path)
    df['total_num'] = pd.to_numeric(df['total_trolleys'], errors='coerce')

    exact_boundaries = []

    for hospital in df['hospital'].unique():
        if hospital == 'National Total':
            continue

        hosp_data = df[df['hospital'] == hospital].copy()
        hosp_data = hosp_data.dropna(subset=['total_num'])
        hosp_data = hosp_data.sort_values('total_num')

        prev = None
        for _, row in hosp_data.iterrows():
            if prev is not None:
                diff = row['total_num'] - prev['total_num']
                if diff == 1 and row['total_color'] != prev['total_color']:
                    # Exact boundary found!
                    exact_boundaries.append({
                        'hospital': hospital,
                        'boundary_type': f"{prev['total_color']}→{row['total_color']}",
                        'below_threshold': int(prev['total_num']),
                        'at_threshold': int(row['total_num']),
                        'proven': True
                    })
            prev = row

    return pd.DataFrame(exact_boundaries)


def print_summary(csv_path):
    """Print a human-readable summary of findings."""

    print("=" * 80)
    print("HSE TROLLEYGAR COLOR THRESHOLD ANALYSIS")
    print("=" * 80)

    thresholds_df = analyze_hospital_thresholds(csv_path)
    exact_df = find_exact_boundaries(csv_path)

    print("\n1. EXACTLY PROVEN BOUNDARIES (1-unit transitions)\n")
    print("-" * 80)

    if not exact_df.empty:
        # Group by boundary type
        for btype in exact_df['boundary_type'].unique():
            print(f"\n{btype.upper()} transitions:")
            subset = exact_df[exact_df['boundary_type'] == btype]
            for _, row in subset.iterrows():
                print(f"  {row['hospital']}: {row['below_threshold']} → {row['at_threshold']}")
    else:
        print("No exact 1-unit boundaries found. Need more data.")

    print("\n" + "=" * 80)
    print("2. INFERRED THRESHOLDS BY HOSPITAL")
    print("=" * 80)

    # Sort by amber threshold
    thresholds_df = thresholds_df.sort_values('amber_threshold', na_position='last')

    print("\n{:<50} {:>8} {:>8}".format("Hospital", "Amber @", "Red @"))
    print("-" * 70)

    for _, row in thresholds_df.iterrows():
        amber = f"{int(row['amber_threshold'])}" if pd.notna(row['amber_threshold']) else "?"
        red = f"{int(row['red_threshold'])}" if pd.notna(row['red_threshold']) else "?"
        print(f"{row['hospital']:<50} {amber:>8} {red:>8}")

    print("\n" + "=" * 80)
    print("3. THRESHOLD PATTERNS")
    print("=" * 80)

    # Look for common thresholds
    if not thresholds_df['amber_threshold'].isna().all():
        amber_counts = thresholds_df['amber_threshold'].value_counts().sort_index()
        print("\nAmber threshold distribution:")
        for thresh, count in amber_counts.items():
            print(f"  Threshold {int(thresh):>3}: {count} hospitals")

    if not thresholds_df['red_threshold'].isna().all():
        red_counts = thresholds_df['red_threshold'].value_counts().sort_index()
        print("\nRed threshold distribution:")
        for thresh, count in red_counts.items():
            print(f"  Threshold {int(thresh):>3}: {count} hospitals")

    # Save results
    thresholds_df.to_csv('inferred_thresholds.csv', index=False)
    if not exact_df.empty:
        exact_df.to_csv('exact_boundaries.csv', index=False)
    print("\nResults saved to inferred_thresholds.csv and exact_boundaries.csv")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = 'jan2026_colors.csv'

    print_summary(csv_path)
