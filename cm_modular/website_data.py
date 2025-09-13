"""
Data preparation functions for website content.
"""
from __future__ import annotations

from typing import List

import pandas as pd
import numpy as np


def prepare_recent_data(df: pd.DataFrame, limit: int) -> dict:
    """Prepare recent rides data for display."""
    if df.empty:
        return {'records': []}
    
    recent = df.tail(limit)
    records = []
    
    for _, row in recent.iterrows():
        # Handle date conversion safely
        date_str = 'Unknown'
        if 't' in row and pd.notna(row['t']):
            try:
                date_str = pd.to_datetime(row['t']).strftime('%d.%m.%Y')
            except:
                date_str = 'Unknown'
        
        record = {
            'length_m': float(row.get('length_m', 0)) if pd.notna(row.get('length_m')) else 0,
            'date': date_str,
            'participants': int(row.get('n_filtered', 0)) if 'n_filtered' in row and pd.notna(row.get('n_filtered')) else None,
        }
        records.append(record)
    
    return {'records': records}


def prepare_leaderboard_data(df: pd.DataFrame, limit: int) -> dict:
    """Prepare leaderboard of longest rides."""
    if 'length_m' not in df.columns:
        return {'records': []}
    
    leaderboard = df.nlargest(limit, 'length_m')
    records = []
    
    for rank, (_, row) in enumerate(leaderboard.iterrows(), 1):
        # Handle date conversion safely
        date_str = 'Unknown'
        if 't' in row and pd.notna(row['t']):
            try:
                date_str = pd.to_datetime(row['t']).strftime('%d.%m.%Y')
            except:
                date_str = 'Unknown'
        
        record = {
            'rank': rank,
            'length_m': float(row['length_m']) if pd.notna(row['length_m']) else 0,
            'date': date_str,
            'participants': int(row.get('n_filtered', 0)) if 'n_filtered' in row and pd.notna(row.get('n_filtered')) else None,
        }
        records.append(record)
    
    return {'records': records}


def prepare_current_stats(df: pd.DataFrame) -> dict:
    """Prepare current statistics."""
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
        try:
            latest_date_str = pd.to_datetime(latest['t']).strftime('%d.%m.%Y - %H:%M')
        except:
            latest_date_str = 'Unknown'
    
    return {
        'n_filtered': int(latest.get('n_filtered')),
        'latest_length': float(latest.get('length_m', 0)) if pd.notna(latest.get('length_m')) else 0,
        'latest_date': latest_date_str,
        'max_length': float(df['length_m'].max())
   }


def prepare_plot_data(df: pd.DataFrame, rel_links: list[str], max_minutes_plot = 120) -> dict:
    """Prepare data for time series plot."""
    if df.empty or 't' not in df.columns:
        return {'x': [], 'y': [], 'links': []}
    
    # Filter out rows without valid timestamps
    valid_df = df[df['t'].notna()].copy()
    
    if not valid_df.empty:
        # Convert timestamps to datetime if they aren't already
        valid_df['t'] = pd.to_datetime(valid_df['t'])
        
        # Get the latest timestamp and filter to last max_minutes_plot minutes
        latest_time = valid_df['t'].max()
        first_plot_time = latest_time - pd.Timedelta(minutes=max_minutes_plot)
        valid_df = valid_df[valid_df['t'] >= first_plot_time]
        
        # Adjust rel_links to match the filtered data
        # We need to find the original indices to map the links correctly
        original_indices = valid_df.index.tolist()
        filtered_links = [rel_links[i] if i < len(rel_links) else '' for i in original_indices] if rel_links else []
    else:
        filtered_links = []
    
    return {
        'x': [t.isoformat() if pd.notna(t) else None for t in valid_df['t']],
        'y': [float(d) if pd.notna(d) else 0 for d in valid_df.get('length_m', [])],
        'links': filtered_links
    }
