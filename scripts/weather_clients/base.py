"""
Base adapter for weather providers.
"""

from abc import ABC, abstractmethod
import pandas as pd


class WeatherAdapter(ABC):
    """Abstract base class for weather provider adapters."""

    @abstractmethod
    def fetch_forecasts(self, resorts: pd.DataFrame) -> pd.DataFrame:
        """
        Fetch forecasts for all resorts, return standardized DataFrame.

        Args:
            resorts: DataFrame with resort data including lat/lon

        Returns:
            DataFrame with columns:
            - resort_name, lat, lon, elevation_m
            - valid_time (datetime)
            - ensemble_member (int)
            - temperature_c (float)
            - precipitation_mm (float)
            - Optional: precipitation_probability, snowfall_cm
        """
        pass
