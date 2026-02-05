"""
Weather client for fetching Open-Meteo forecast data.
Free API, no key required, includes ensemble forecasts.
https://open-meteo.com/
"""

import time
from typing import List, Dict, Any
import requests
import pandas as pd
import numpy as np


# Open-Meteo API endpoint
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

# Rate limiting: Open-Meteo allows 10,000 requests/day on free tier
# We'll batch requests and add small delays
REQUEST_DELAY = 0.1  # seconds between requests


def fetch_ensemble_forecast(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch ensemble forecast for a single location.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dictionary with forecast data
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "precipitation"],
        "forecast_days": 7,
        "models": "gfs_seamless",  # GFS ensemble with 31 members
    }

    response = requests.get(ENSEMBLE_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_standard_forecast(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch standard (non-ensemble) forecast for a single location.
    Falls back to this if ensemble API has issues.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Dictionary with forecast data
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ["temperature_2m", "precipitation_probability", "precipitation", "snowfall"],
        "forecast_days": 7,
    }

    response = requests.get(FORECAST_URL, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def fetch_forecasts_batch(resorts: pd.DataFrame, use_ensemble: bool = True) -> pd.DataFrame:
    """
    Fetch forecasts for all resorts.

    Args:
        resorts: DataFrame with resort data including lat/lon
        use_ensemble: Whether to use ensemble API (more requests but probabilistic)

    Returns:
        DataFrame with forecast data for all locations
    """
    all_forecasts = []
    total = len(resorts)

    print(f"Fetching forecasts for {total} resorts...")

    for idx, resort in resorts.iterrows():
        try:
            if use_ensemble:
                data = fetch_ensemble_forecast(resort['lat'], resort['lon'])
                forecast = parse_ensemble_response(data, resort)
            else:
                data = fetch_standard_forecast(resort['lat'], resort['lon'])
                forecast = parse_standard_response(data, resort)

            all_forecasts.append(forecast)

            if (idx + 1) % 10 == 0:
                print(f"  Progress: {idx + 1}/{total}")

            time.sleep(REQUEST_DELAY)

        except Exception as e:
            print(f"  Warning: Failed to fetch {resort['name']}: {e}")
            continue

    if not all_forecasts:
        return pd.DataFrame()

    return pd.concat(all_forecasts, ignore_index=True)


def parse_ensemble_response(data: Dict[str, Any], resort: pd.Series) -> pd.DataFrame:
    """
    Parse ensemble API response into DataFrame.

    The ensemble API returns multiple members (model runs) which we use
    for probabilistic forecasting.
    """
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    # Get all temperature and precipitation ensemble members
    temp_keys = [k for k in hourly.keys() if k.startswith("temperature_2m")]
    precip_keys = [k for k in hourly.keys() if k.startswith("precipitation")]

    rows = []
    for i, time_str in enumerate(times):
        # Get values from all ensemble members
        temps = [hourly[k][i] for k in temp_keys if hourly[k][i] is not None]
        precips = [hourly[k][i] for k in precip_keys if hourly[k][i] is not None]

        if not temps or not precips:
            continue

        for member_idx, (temp, precip) in enumerate(zip(temps, precips)):
            rows.append({
                "resort_name": resort["name"],
                "lat": resort["lat"],
                "lon": resort["lon"],
                "elevation_m": resort["elevation_m"],
                "valid_time": pd.to_datetime(time_str),
                "ensemble_member": member_idx,
                "temperature_c": temp,
                "precipitation_mm": precip,
            })

    return pd.DataFrame(rows)


def parse_standard_response(data: Dict[str, Any], resort: pd.Series) -> pd.DataFrame:
    """
    Parse standard forecast API response into DataFrame.

    Uses precipitation_probability as a proxy for ensemble spread.
    """
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    precip_probs = hourly.get("precipitation_probability", [])
    precips = hourly.get("precipitation", [])
    snowfalls = hourly.get("snowfall", [])

    rows = []
    for i, time_str in enumerate(times):
        if temps[i] is None:
            continue

        rows.append({
            "resort_name": resort["name"],
            "lat": resort["lat"],
            "lon": resort["lon"],
            "elevation_m": resort["elevation_m"],
            "valid_time": pd.to_datetime(time_str),
            "ensemble_member": 0,  # Single deterministic forecast
            "temperature_c": temps[i],
            "precipitation_mm": precips[i] if precips[i] else 0,
            "precipitation_probability": precip_probs[i] if precip_probs[i] else 0,
            "snowfall_cm": snowfalls[i] if snowfalls[i] else 0,
        })

    return pd.DataFrame(rows)
