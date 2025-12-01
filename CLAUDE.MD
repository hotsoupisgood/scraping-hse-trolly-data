# HSE Trolley Data Project - Session Notes

## Current Status

We're working on mapping HSE hospital regional reorganization between 2023 and 2024.

### What We Discovered

**MAJOR REGIONAL REORGANIZATION between 2023 and 2024:**

**2023 Structure (3 regions):**
- HSE Dublin and North East
- HSE Dublin and Midlands
- HSE Dublin and South East *(this was a MEGA-REGION containing all South, Southwest, West, and Northwest hospitals!)*

**2024+ Structure (6 regions):**
- HSE Dublin & North East (note: uses "&" instead of "and")
- HSE Dublin & Midlands
- HSE Dublin & South East (now truly SE only)
- HSE South West (NEW - split from old mega-region)
- HSE Mid West (NEW - split from old mega-region)
- HSE West & North West (NEW - split from old mega-region)

### Files Created

1. **`hospital_region_mapping.py`** - Contains:
   - `HOSPITAL_REGION_MAP_2023` - Pre-2024 hospital→region mapping
   - `HOSPITAL_REGION_MAP_2024_CORRECTED` - Post-2024 hospital→region mapping
   - `get_hospital_region(hospital_name, year)` - Function to get region based on year
   - `normalize_to_2024_regions(df)` - Function to normalize all data to 2024 regions

2. **`validate_all.py`** - Consolidated validation (combines validate_scraper.py and validate_csvs.py into one tool)

### What Still Needs Checking

The 2024 data shows some **geographically odd groupings** that need verification:
- **Bantry General Hospital** → "HSE Dublin & South East" (Bantry is in Cork, seems like it should be South West?)
- **Ennis Hospital** → "HSE South West" (Ennis is in Clare, seems like it should be Mid West?)
- **Galway University Hospital** → "HSE Mid West" (Galway seems like it should be West & North West?)

These mappings are based on ACTUAL position in the 2024 scraped data (hospitals appear before their regional "Total" row), but they seem geographically wrong.

### Next Steps

1. **Verify the odd 2024 mappings** - Need to check multiple 2024 dates to confirm:
   ```python
   # Check if Galway is consistently in Mid West or if data structure changed
   # Check multiple dates: Jan 2024, Jun 2024, Nov 2024
   ```

2. **Complete the mapping file** - Once verified, the mapping can be used to:
   - Normalize all 2023 data to 2024 regional structure
   - Enable consistent cross-year analysis
   - Handle both "and" and "&" naming conventions

3. **Clean up old validation files** - Can delete:
   - `validate_scraper.py`
   - `validate_csvs.py`

   Use `validate_all.py` instead.

### Data Files

- **Main dataset**: `data/uec_data_2023_2025_full.csv`
- **Old segmented files** (can probably delete):
  - `data/uec_data_2023p1.csv`
  - `data/uec_data_2023p2.csv`
  - `data/uec_data_2024p1.csv`
  - etc.

### Key Insight

The HSE didn't just rename regions (and → &), they fundamentally **reorganized which hospitals belong to which administrative regions**. This means:

- Can't just do a simple string replacement
- Need year-aware mapping to correctly analyze trends
- 2023 "Dublin and South East" data needs to be split into 4 separate regions for comparison with 2024+

### Command to Verify Mappings

```bash
./venv/bin/python3 << 'EOF'
import pandas as pd

df = pd.read_csv('data/uec_data_2023_2025_full.csv')

# Check multiple 2024 dates to verify regional groupings
for date in ['01/01/2024', '01/06/2024', '01/11/2024']:
    print(f"\n{date}")
    print("="*80)
    date_df = df[df['Date'] == date]

    current_hospitals = []
    for _, row in date_df.iterrows():
        hospital = row['Hospital']
        if 'Total' in hospital:
            if current_hospitals:
                print(f"\n{hospital}:")
                for h in current_hospitals:
                    print(f"  - {h}")
            current_hospitals = []
        else:
            current_hospitals.append(hospital)
EOF
```

This will show whether Galway/Ennis/Bantry are consistently in those (geographically odd) regions throughout 2024.
