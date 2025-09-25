"""
Data preparation functions for website content.
"""
from __future__ import annotations

from typing import List
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np


BERLIN_TZ = ZoneInfo("Europe/Berlin")
UTC_TZ = ZoneInfo("UTC")


def _to_berlin(dt_val):
    """Convert a datetime-like value to Europe/Berlin timezone.

    Assumptions:
      - Naive datetime or parseable string is interpreted as UTC (as filenames / data originate in UTC)
      - If tz-aware, it's converted to Berlin.
    Returns a timezone-aware datetime in Europe/Berlin, or None on failure.
    """
    if pd.isna(dt_val):
        return None
    try:
        dt = pd.to_datetime(dt_val, utc=True)  # ensure result is tz-aware UTC
        # pandas may already localize if tz info present; enforce conversion to UTC first
        if getattr(dt, 'tzinfo', None) is None:
            # localize as UTC explicitly (shouldn't happen due to utc=True, but safety)
            dt = dt.tz_localize(UTC_TZ)  # type: ignore[attr-defined]
        return dt.tz_convert(BERLIN_TZ)
    except Exception:
        return None


def prepare_recent_data(df: pd.DataFrame, limit: int) -> dict:
    """Prepare recent rides data for display (dates shown in Europe/Berlin local time)."""
    if df.empty:
        return {'records': []}
    
    recent = df.tail(limit)
    records = []
    
    for _, row in recent.iterrows():
        # Handle date conversion safely
        date_str = 'Unknown'
        if 't' in row and pd.notna(row['t']):
            local_dt = _to_berlin(row['t'])
            if local_dt is not None:
                date_str = local_dt.strftime('%d.%m.%Y')
        
        record = {
            'length_m': float(row.get('length_m', 0)) if pd.notna(row.get('length_m')) else 0,
            'date': date_str,
            'participants': int(row.get('n_filtered', 0)) if 'n_filtered' in row and pd.notna(row.get('n_filtered')) else None,
            'city': str(row.get('city', 'Unknown')) if pd.notna(row.get('city')) else 'Unknown',
        }
        records.append(record)
    
    return {'records': records}

def prepare_city_leaderboard_data(combined_df: pd.DataFrame, limit: int = 10) -> dict:
    """Prepare leaderboard of cities by their most recent longest route (dates in Berlin time)."""
    if combined_df.empty or 'city' not in combined_df.columns:
        return {'records': []}
    
    city_records = []
    
    # Group by city and get the most recent data for each city
    for city in combined_df['city'].unique():
        city_df = combined_df[combined_df['city'] == city]
        
        if city_df.empty:
            continue
            
        # Sort by timestamp to get most recent data
        if 't' in city_df.columns:
            city_df_sorted = city_df.dropna(subset=['t']).sort_values('t')
            if not city_df_sorted.empty:
                latest_data = city_df_sorted.iloc[-1]
            else:
                latest_data = city_df.iloc[-1]  # Fallback to last row
        else:
            latest_data = city_df.iloc[-1]  # Use last row if no timestamp
        
        # Handle date conversion safely
        date_str = 'Unknown'
        if 't' in latest_data and pd.notna(latest_data['t']):
            local_dt = _to_berlin(latest_data['t'])
            if local_dt is not None:
                date_str = local_dt.strftime('%d.%m.%Y')
        
        city_record = {
            'city': str(city),
            'length_m': float(latest_data.get('length_m', 0)) if pd.notna(latest_data.get('length_m')) else 0,
            'date': date_str,
            'participants': int(latest_data.get('n_filtered', 0)) if 'n_filtered' in latest_data and pd.notna(latest_data.get('n_filtered')) else None,
        }
        city_records.append(city_record)
    
    # Sort cities by length (descending) and take top N
    city_records.sort(key=lambda x: x['length_m'], reverse=True)
    city_records = city_records[:limit]
    
    # Add ranking
    for rank, record in enumerate(city_records, 1):
        record['rank'] = rank
    
    return {'records': city_records}


def prepare_current_stats(df: pd.DataFrame) -> dict:
    """Prepare current statistics (timestamps shown in Berlin time)."""
    if df.empty:
        return {
            'total_rides': 0,
            'latest_length': 0,
            'latest_date': 'No data',
            'avg_length': 0,
            'total_distance': 0,
        }
    
    latest = df.loc[df.index[-1]] if not df.empty else {}
    
    # Handle timestamp conversion safely
    latest_date_str = 'Unknown'
    if 't' in latest and pd.notna(latest['t']):
        local_dt = _to_berlin(latest['t'])
        if local_dt is not None:
            latest_date_str = local_dt.strftime('%d.%m.%Y - %H:%M')
    
    return {
        'n_filtered': int(latest.get('n_filtered')),
        'latest_length': float(latest.get('length_m', 0)) if pd.notna(latest.get('length_m')) else 0,
        'latest_date': latest_date_str,
        'max_length': float(df['length_m'].max())
   }


def prepare_plot_data(df: pd.DataFrame, rel_links: list[str], max_minutes_plot = 120) -> dict:
    """Prepare data for time series plot.

    All timestamps returned in 'x' are converted to Europe/Berlin timezone (ISO 8601 with offset),
    while filtering assumes original 't' values are in UTC (filename-origin timestamps).
    """
    if df.empty or 't' not in df.columns:
        return {'x': [], 'y': [], 'links': [], 'cities': []}
    
    # Filter out rows without valid timestamps
    valid_df = df[df['t'].notna()].copy()
    
    if not valid_df.empty:
        # Convert timestamps to datetime (assumed UTC) then convert to Berlin
        valid_df['t'] = pd.to_datetime(valid_df['t'], utc=True).dt.tz_convert(BERLIN_TZ)

        # Get the latest timestamp and filter to last max_minutes_plot minutes
        latest_time = valid_df['t'].max()
        first_plot_time = latest_time - pd.Timedelta(minutes=max_minutes_plot)
        valid_df = valid_df[valid_df['t'] >= first_plot_time]

        # Adjust rel_links to match the filtered data
        original_indices = valid_df.index.tolist()
        filtered_links = [rel_links[i] if i < len(rel_links) else '' for i in original_indices] if rel_links else []
    else:
        filtered_links = []
    
    # Extract city information for each data point
    cities = [str(city) if pd.notna(city) else 'Unknown' for city in valid_df.get('city', ['Unknown'] * len(valid_df))]
    
    return {
        'x': [t.isoformat() if pd.notna(t) else None for t in valid_df['t']],  # already Berlin tz-aware
        'y': [float(d) if pd.notna(d) else 0 for d in valid_df.get('length_m', [])],
        'links': filtered_links,
        'cities': cities
    }
