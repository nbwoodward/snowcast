"""
Weather provider clients.

Usage:
    from weather_clients import get_weather_client

    client = get_weather_client()  # Uses WEATHER_PROVIDER env var or defaults to 'openmeteo'
    forecast_df = client.fetch_forecasts(resorts)
"""

import os

from .base import WeatherAdapter
from .openmeteo import OpenMeteoAdapter
from .pirateweather import PirateWeatherAdapter
from .google import GoogleWeatherAdapter


def get_weather_client(provider: str = None) -> WeatherAdapter:
    """
    Get a weather client instance.

    Args:
        provider: Weather provider name ('openmeteo' or 'pirateweather').
                  If not specified, reads from WEATHER_PROVIDER environment
                  variable, defaulting to 'openmeteo'.

    Returns:
        WeatherAdapter instance

    Raises:
        ValueError: If provider is unknown
    """
    provider = provider or os.environ.get('WEATHER_PROVIDER', 'openmeteo')

    if provider == 'openmeteo':
        return OpenMeteoAdapter()
    elif provider == 'pirateweather':
        return PirateWeatherAdapter()
    elif provider == 'google':
        return GoogleWeatherAdapter()
    else:
        raise ValueError(f"Unknown weather provider: {provider}")


__all__ = [
    'WeatherAdapter',
    'OpenMeteoAdapter',
    'PirateWeatherAdapter',
    'GoogleWeatherAdapter',
    'get_weather_client',
]
