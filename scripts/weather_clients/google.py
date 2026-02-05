"""
Google Maps Weather API adapter.
Requires API key from Google Cloud Platform.
https://developers.google.com/maps/documentation/weather
"""

import os
import time
from typing import Dict, Any

import requests
import pandas as pd

from .base import WeatherAdapter


# Google Weather API endpoint
API_URL = "https://weather.googleapis.com/v1/forecast/hours:lookup"

# Rate limiting
REQUEST_DELAY = 0.1  # seconds between requests


class GoogleWeatherAdapter(WeatherAdapter):
    """Adapter for Google Maps Weather API."""

    def __init__(self, api_key: str = None):
        """
        Initialize the adapter.

        Args:
            api_key: Google Cloud Platform API key with Weather API enabled.
                     If not provided, reads from GCP_API_KEY environment variable.
        """
        self.api_key = api_key or os.environ.get('GCP_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Google Cloud API key required. Set GCP_API_KEY "
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
        Fetch hourly forecast for a single location.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dictionary with forecast data
        """
        all_hours = []
        page_token = None

        while True:
            params = {
                "key": self.api_key,
                "location.latitude": lat,
                "location.longitude": lon,
                "hours": 168,  # 7 days of hourly data
                "pageSize": 168,  # Request all hours in one page
            }
            if page_token:
                params["pageToken"] = page_token

            response = requests.get(API_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            all_hours.extend(data.get("forecastHours", []))

            # Check for more pages
            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return {"forecastHours": all_hours}

    def _parse_response(self, data: Dict[str, Any], resort: pd.Series) -> pd.DataFrame:
        """
        Parse Google Weather API response into DataFrame.

        Converts the hourly forecast data to our standard format.
        """
        forecast_hours = data.get("forecastHours", [])

        rows = []
        for hour in forecast_hours:
            # Parse time from interval
            interval = hour.get("interval", {})
            start_time = interval.get("startTime")
            if not start_time:
                continue

            valid_time = pd.to_datetime(start_time)

            # Get temperature (API returns Celsius by default)
            temp_obj = hour.get("temperature", {})
            temperature = temp_obj.get("degrees")
            if temperature is None:
                continue

            # Get precipitation data
            precip_obj = hour.get("precipitation", {})

            # Precipitation probability
            prob_obj = precip_obj.get("probability", {})
            precip_probability = prob_obj.get("percent", 0)

            # Quantitative precipitation forecast (liquid equivalent in mm)
            qpf_obj = precip_obj.get("qpf", {})
            precip_mm = qpf_obj.get("quantity", 0) or 0

            # Snow QPF (liquid water equivalent in mm)
            snow_qpf_obj = precip_obj.get("snowQpf", {})
            snow_mm = snow_qpf_obj.get("quantity", 0) or 0
            # Convert mm to cm
            snowfall_cm = snow_mm / 10

            rows.append({
                "resort_name": resort["name"],
                "lat": resort["lat"],
                "lon": resort["lon"],
                "elevation_m": resort["elevation_m"],
                "valid_time": valid_time,
                "ensemble_member": 0,  # Single deterministic forecast
                "temperature_c": temperature,
                "precipitation_mm": precip_mm,
                "precipitation_probability": precip_probability,
                "snowfall_cm": snowfall_cm,
            })

        return pd.DataFrame(rows)
