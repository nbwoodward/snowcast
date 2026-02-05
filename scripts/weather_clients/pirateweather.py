"""
Pirate Weather adapter.
Requires API key from https://pirateweather.net/
"""

import os
import time
from typing import Dict, Any

import requests
import pandas as pd

from .base import WeatherAdapter


# Pirate Weather API endpoint
API_URL = "https://api.pirateweather.net/forecast"

# Rate limiting
REQUEST_DELAY = 0.1  # seconds between requests


class PirateWeatherAdapter(WeatherAdapter):
    """Adapter for Pirate Weather API."""

    def __init__(self, api_key: str = None):
        """
        Initialize the adapter.

        Args:
            api_key: Pirate Weather API key. If not provided, reads from
                     PIRATE_WEATHER_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get('PIRATE_WEATHER_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Pirate Weather API key required. Set PIRATE_WEATHER_API_KEY "
                "environment variable or pass api_key to constructor."
            )

    def fetch_forecasts(self, resorts: pd.DataFrame) -> pd.DataFrame:
        """
        Fetch forecasts for all resorts.

        Args:
            resorts: DataFrame with resort data including lat/lon

        Returns:
            DataFrame with forecast data for all locations
        """
        all_forecasts = []
        total = len(resorts)

        print(f"Fetching forecasts for {total} resorts...")

        for idx, resort in resorts.iterrows():
            try:
                data = self._fetch_forecast(resort['lat'], resort['lon'])
                forecast = self._parse_response(data, resort)
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

    def _fetch_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Fetch forecast for a single location.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dictionary with forecast data
        """
        url = f"{API_URL}/{self.api_key}/{lat},{lon}"
        params = {
            "extend": "hourly",
            "units": "si",
            "version": "2",
        }

        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _parse_response(self, data: Dict[str, Any], resort: pd.Series) -> pd.DataFrame:
        """
        Parse Pirate Weather API response into DataFrame.

        The API returns hourly data which we convert to our standard format.
        """
        hourly = data.get("hourly", {})
        hourly_data = hourly.get("data", [])

        rows = []
        for hour in hourly_data:
            # Convert Unix timestamp to datetime
            timestamp = hour.get("time")
            if timestamp is None:
                continue

            valid_time = pd.to_datetime(timestamp, unit='s', utc=True)

            # Get weather data
            temperature = hour.get("temperature")  # Already in Celsius with units=si
            precip_intensity = hour.get("precipIntensity", 0)  # mm/hr
            precip_probability = hour.get("precipProbability", 0)  # 0-1
            precip_type = hour.get("precipType")
            snow_accumulation = hour.get("snowAccumulation", 0)  # cm

            if temperature is None:
                continue

            rows.append({
                "resort_name": resort["name"],
                "lat": resort["lat"],
                "lon": resort["lon"],
                "elevation_m": resort["elevation_m"],
                "valid_time": valid_time,
                "ensemble_member": 0,  # Single deterministic forecast
                "temperature_c": temperature,
                "precipitation_mm": precip_intensity,  # mm/hr intensity
                "precipitation_probability": precip_probability * 100,  # Convert to percentage
                "snowfall_cm": snow_accumulation if precip_type == "snow" else 0,
            })

        return pd.DataFrame(rows)
