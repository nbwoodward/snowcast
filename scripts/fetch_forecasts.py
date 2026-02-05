#!/usr/bin/env python3
"""
Main script to fetch weather forecasts and generate snow predictions.
Run by GitHub Action daily or locally for testing.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from weather_client import fetch_forecasts_batch
from snow_calculator import calculate_resort_forecast, calculate_region_summary


# Paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "data"

RESORTS_FILE = DATA_DIR / "resorts.csv"
REGIONS_FILE = DATA_DIR / "regions.json"
OUTPUT_FILE = OUTPUT_DIR / "forecasts.json"


def load_resorts() -> pd.DataFrame:
    """Load ski resort data from CSV."""
    df = pd.read_csv(RESORTS_FILE)
    print(f"Loaded {len(df)} resorts")
    return df


def load_regions() -> list:
    """Load region definitions from JSON."""
    with open(REGIONS_FILE) as f:
        data = json.load(f)
    print(f"Loaded {len(data['regions'])} regions")
    return data['regions']


def assign_resorts_to_regions(resorts: pd.DataFrame, regions: list) -> dict:
    """
    Assign each resort to its region.

    Args:
        resorts: DataFrame with resort data
        regions: List of region dictionaries

    Returns:
        Dictionary mapping region_id to list of resort dictionaries
    """
    region_resorts = {r['id']: [] for r in regions}

    for _, resort in resorts.iterrows():
        region_id = resort.get('region_id')
        if region_id and region_id in region_resorts:
            region_resorts[region_id].append(resort.to_dict())
        else:
            # Fallback: assign by bounding box
            for region in regions:
                bounds = region['bounds']
                if (bounds['min_lat'] <= resort['lat'] <= bounds['max_lat'] and
                    bounds['min_lon'] <= resort['lon'] <= bounds['max_lon']):
                    region_resorts[region['id']].append(resort.to_dict())
                    break

    return region_resorts


def main():
    """Main entry point."""
    print(f"Starting forecast fetch at {datetime.now(timezone.utc).isoformat()}")

    # Load data
    resorts = load_resorts()
    regions = load_regions()

    # Assign resorts to regions
    region_resorts = assign_resorts_to_regions(resorts, regions)

    # Fetch forecasts from Open-Meteo
    print("\nFetching weather forecasts from Open-Meteo...")
    try:
        # Try ensemble first for probabilistic forecasts
        forecast_df = fetch_forecasts_batch(resorts, use_ensemble=True)
    except Exception as e:
        print(f"Ensemble API failed ({e}), falling back to standard forecast...")
        forecast_df = fetch_forecasts_batch(resorts, use_ensemble=False)

    if forecast_df.empty:
        print("Warning: No forecast data retrieved")
        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "forecast_init_time": datetime.now(timezone.utc).isoformat(),
            "regions": []
        }
    else:
        print(f"\nRetrieved {len(forecast_df)} forecast data points")

        # Calculate forecasts for each resort
        print("\nCalculating snow probabilities...")
        all_region_data = []

        for region in regions:
            region_id = region['id']
            resorts_in_region = region_resorts.get(region_id, [])

            if not resorts_in_region:
                print(f"  {region['name']}: No resorts")
                continue

            # Calculate forecast for each resort
            resort_forecasts = []
            for resort in resorts_in_region:
                forecast = calculate_resort_forecast(resort, forecast_df)
                resort_forecasts.append(forecast)

            # Calculate region summary
            region_summary = calculate_region_summary(region, resort_forecasts)
            all_region_data.append(region_summary)

            print(f"  {region['name']}: {region_summary['resorts_with_snow']}/{region_summary['total_resorts']} resorts with snow, avg prob: {region_summary['avg_snow_probability']:.0%}")

        # Sort regions by average snow probability
        all_region_data.sort(key=lambda r: -r['avg_snow_probability'])

        output = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "forecast_init_time": datetime.now(timezone.utc).isoformat(),
            "regions": all_region_data
        }

    # Write output
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\nForecast written to {OUTPUT_FILE}")
    print(f"Total regions: {len(output['regions'])}")


if __name__ == "__main__":
    main()
