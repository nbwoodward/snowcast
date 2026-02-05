"""
Snow probability calculator for ski resort forecasts.

Uses ensemble forecasts to calculate:
- Probability of snow
- Expected snow accumulation
- Confidence intervals
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any


# Temperature threshold for snow (Celsius)
# Snow typically forms when surface temp is at or below 1C
SNOW_TEMP_THRESHOLD_C = 1.0

# Minimum precipitation for meaningful snow (mm water equivalent)
MIN_PRECIP_MM = 0.5

# Snow to liquid ratio (10:1 is typical, can vary 5:1 to 20:1)
SNOW_RATIO = 10.0

# Temperature lapse rate (C per 1000m elevation gain)
# Standard atmosphere: -6.5C/1000m
LAPSE_RATE_C_PER_KM = -6.5


def adjust_temperature_for_elevation(
    temp_c: float,
    forecast_elevation_m: float,
    resort_elevation_m: float
) -> float:
    """
    Adjust temperature from forecast elevation to resort elevation.

    Args:
        temp_c: Temperature at forecast point (Celsius)
        forecast_elevation_m: Elevation of the forecast point (meters)
        resort_elevation_m: Elevation of the resort (meters)

    Returns:
        Adjusted temperature (Celsius)
    """
    elevation_diff_km = (resort_elevation_m - forecast_elevation_m) / 1000.0
    adjustment = LAPSE_RATE_C_PER_KM * elevation_diff_km
    return temp_c + adjustment


def calculate_snow_from_precip(precip_mm: float) -> float:
    """
    Convert precipitation (mm water equivalent) to snow (cm).

    Args:
        precip_mm: Precipitation in mm

    Returns:
        Snow accumulation in cm
    """
    return precip_mm * SNOW_RATIO / 10.0  # mm to cm


def is_snow_event(temp_c: float, precip_mm: float) -> bool:
    """
    Determine if conditions produce snow.

    Args:
        temp_c: Temperature in Celsius
        precip_mm: Precipitation in mm

    Returns:
        True if snow expected, False otherwise
    """
    return temp_c <= SNOW_TEMP_THRESHOLD_C and precip_mm >= MIN_PRECIP_MM


def calculate_resort_forecast(
    resort: Dict[str, Any],
    forecast_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Calculate snow forecast for a single resort.

    Args:
        resort: Resort dictionary with name, lat, lon, elevation_m
        forecast_df: DataFrame with ensemble forecasts

    Returns:
        Dictionary with forecast results
    """
    # Filter forecasts for this resort
    resort_forecasts = forecast_df[
        forecast_df['resort_name'] == resort['name']
    ].copy()

    if resort_forecasts.empty:
        return {
            'name': resort['name'],
            'country': resort['country'],
            'lat': resort['lat'],
            'lon': resort['lon'],
            'elevation_m': resort['elevation_m'],
            'snow_probability': 0,
            'expected_snow_cm': 0,
            'snow_range_cm': [0, 0],
            'daily_forecast': []
        }

    # Check if we have ensemble data or standard forecast
    has_ensemble = resort_forecasts['ensemble_member'].nunique() > 1
    has_direct_snowfall = 'snowfall_cm' in resort_forecasts.columns

    if has_direct_snowfall and not has_ensemble:
        # Use direct snowfall data from standard forecast
        return calculate_from_standard_forecast(resort, resort_forecasts)
    else:
        # Use ensemble-based calculation
        return calculate_from_ensemble_forecast(resort, resort_forecasts)


def calculate_from_ensemble_forecast(
    resort: Dict[str, Any],
    forecast_df: pd.DataFrame
) -> Dict[str, Any]:
    """Calculate snow forecast from ensemble data."""

    # Open-Meteo forecasts are already at approximate surface level
    # We apply a small elevation adjustment assuming forecast is for ~500m
    base_elevation = 500  # Approximate model surface elevation

    forecast_df = forecast_df.copy()
    forecast_df['adjusted_temp_c'] = forecast_df['temperature_c'].apply(
        lambda t: adjust_temperature_for_elevation(t, base_elevation, resort['elevation_m'])
    )

    # Calculate snow for each ensemble member and time step
    forecast_df['is_snow'] = forecast_df.apply(
        lambda row: is_snow_event(row['adjusted_temp_c'], row['precipitation_mm']),
        axis=1
    )
    forecast_df['snow_cm'] = forecast_df.apply(
        lambda row: calculate_snow_from_precip(row['precipitation_mm']) if row['is_snow'] else 0,
        axis=1
    )

    # Calculate total snow per ensemble member
    ensemble_totals = forecast_df.groupby('ensemble_member')['snow_cm'].sum()

    # Overall statistics
    snow_probability = (ensemble_totals > 0).mean()
    expected_snow = ensemble_totals.mean()
    p10 = ensemble_totals.quantile(0.1)
    p90 = ensemble_totals.quantile(0.9)

    # Daily breakdown
    forecast_df['date'] = forecast_df['valid_time'].dt.date
    daily_forecasts = []

    for date in sorted(forecast_df['date'].unique()):
        day_df = forecast_df[forecast_df['date'] == date]
        daily_ensemble = day_df.groupby('ensemble_member')['snow_cm'].sum()
        daily_prob = (daily_ensemble > 0).mean()
        daily_expected = daily_ensemble.mean()

        daily_forecasts.append({
            'date': str(date),
            'prob': round(float(daily_prob), 2),
            'cm': round(float(daily_expected), 1)
        })

    return {
        'name': resort['name'],
        'country': resort['country'],
        'lat': float(resort['lat']),
        'lon': float(resort['lon']),
        'elevation_m': int(resort['elevation_m']),
        'snow_probability': round(float(snow_probability), 2),
        'expected_snow_cm': round(float(expected_snow), 1),
        'snow_range_cm': [round(float(p10), 1), round(float(p90), 1)],
        'daily_forecast': daily_forecasts
    }


def calculate_from_standard_forecast(
    resort: Dict[str, Any],
    forecast_df: pd.DataFrame
) -> Dict[str, Any]:
    """Calculate snow forecast from standard (non-ensemble) data."""

    forecast_df = forecast_df.copy()

    # Use direct snowfall if available, otherwise calculate from precip + temp
    if 'snowfall_cm' in forecast_df.columns:
        total_snow = forecast_df['snowfall_cm'].sum()
    else:
        base_elevation = 500
        forecast_df['adjusted_temp_c'] = forecast_df['temperature_c'].apply(
            lambda t: adjust_temperature_for_elevation(t, base_elevation, resort['elevation_m'])
        )
        forecast_df['snow_cm'] = forecast_df.apply(
            lambda row: calculate_snow_from_precip(row['precipitation_mm'])
            if row['adjusted_temp_c'] <= SNOW_TEMP_THRESHOLD_C else 0,
            axis=1
        )
        total_snow = forecast_df['snow_cm'].sum()

    # Use precipitation probability as snow probability proxy
    if 'precipitation_probability' in forecast_df.columns:
        # Average probability when there's meaningful precip
        cold_hours = forecast_df[forecast_df['temperature_c'] <= SNOW_TEMP_THRESHOLD_C]
        if len(cold_hours) > 0:
            snow_probability = cold_hours['precipitation_probability'].mean() / 100.0
        else:
            snow_probability = 0
    else:
        snow_probability = 1.0 if total_snow > 0 else 0

    # Daily breakdown
    forecast_df['date'] = forecast_df['valid_time'].dt.date
    daily_forecasts = []

    for date in sorted(forecast_df['date'].unique()):
        day_df = forecast_df[forecast_df['date'] == date]

        if 'snowfall_cm' in day_df.columns:
            daily_snow = day_df['snowfall_cm'].sum()
        else:
            daily_snow = day_df['snow_cm'].sum() if 'snow_cm' in day_df.columns else 0

        if 'precipitation_probability' in day_df.columns:
            cold_day = day_df[day_df['temperature_c'] <= SNOW_TEMP_THRESHOLD_C]
            daily_prob = cold_day['precipitation_probability'].mean() / 100.0 if len(cold_day) > 0 else 0
        else:
            daily_prob = 1.0 if daily_snow > 0 else 0

        daily_forecasts.append({
            'date': str(date),
            'prob': round(float(daily_prob), 2),
            'cm': round(float(daily_snow), 1)
        })

    return {
        'name': resort['name'],
        'country': resort['country'],
        'lat': float(resort['lat']),
        'lon': float(resort['lon']),
        'elevation_m': int(resort['elevation_m']),
        'snow_probability': round(float(snow_probability), 2),
        'expected_snow_cm': round(float(total_snow), 1),
        'snow_range_cm': [round(float(total_snow * 0.5), 1), round(float(total_snow * 1.5), 1)],
        'daily_forecast': daily_forecasts
    }


def calculate_region_summary(
    region: Dict[str, Any],
    resort_forecasts: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate summary statistics for a region.

    Args:
        region: Region dictionary with id, name, bounds
        resort_forecasts: List of resort forecast dictionaries

    Returns:
        Region summary dictionary
    """
    if not resort_forecasts:
        return {
            'id': region['id'],
            'name': region['name'],
            'avg_snow_probability': 0,
            'resorts_with_snow': 0,
            'total_resorts': 0,
            'best_resort': None,
            'resorts': []
        }

    probabilities = [r['snow_probability'] for r in resort_forecasts]
    avg_prob = sum(probabilities) / len(probabilities)
    resorts_with_snow = sum(1 for r in resort_forecasts if r['snow_probability'] > 0.3)

    # Find best resort by expected snow
    best_resort = max(resort_forecasts, key=lambda r: r['expected_snow_cm'])

    return {
        'id': region['id'],
        'name': region['name'],
        'avg_snow_probability': round(avg_prob, 2),
        'resorts_with_snow': resorts_with_snow,
        'total_resorts': len(resort_forecasts),
        'best_resort': {
            'name': best_resort['name'],
            'expected_snow_cm': best_resort['expected_snow_cm']
        } if best_resort['expected_snow_cm'] > 0 else None,
        'resorts': sorted(resort_forecasts, key=lambda r: -r['snow_probability'])
    }
