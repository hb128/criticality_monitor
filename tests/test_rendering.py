"""
Tests for the rendering module.

Verify that render_map() returns valid HTML without file IO.
"""
import pytest
import pandas as pd
import numpy as np
from cm_modular.rendering import render_map
from cm_modular.pipeline import PipelineResult, PipelineConfig


def test_render_map_returns_html_string():
    """render_map should return valid HTML without writing files."""
    # Minimal result with no path
    result = PipelineResult(has_path=False)
    config = PipelineConfig(city="hamburg")
    
    html = render_map(result, config)
    
    assert isinstance(html, str)
    assert "<!DOCTYPE html>" in html or "<html>" in html.lower()
    assert len(html) > 100  # Not empty


def test_render_map_with_path():
    """render_map should include path polyline when has_path=True."""
    # Create minimal result with a simple path
    filtered = pd.DataFrame({
        'lat': [53.55, 53.56, 53.57],
        'lon': [10.0, 10.01, 10.02],
        'timestamp': [1000, 1001, 1002],
        'cluster': [0, 0, 0],
        'keep': [True, True, True]
    })
    
    result = PipelineResult(
        has_path=True,
        filtered=filtered,
        outliers=pd.DataFrame(),
        path_indices=[0, 1, 2],
        segment_metrics=[
            {'start': 0, 'stop': 1, 'geo_len': 100.0, 'angle_len': 100.0},
            {'start': 1, 'stop': 2, 'geo_len': 100.0, 'angle_len': 100.0}
        ],
        length_m=200.0
    )
    config = PipelineConfig(city="hamburg")
    
    html = render_map(result, config)
    
    assert isinstance(html, str)
    assert len(html) > 1000  # Should be substantial
    # Map should contain coordinates (in some format)
    assert "53.5" in html or "53_5" in html  # Latitude appears somewhere


def test_render_map_with_outliers():
    """render_map should handle outliers layer."""
    filtered = pd.DataFrame({
        'lat': [53.55, 53.56],
        'lon': [10.0, 10.01],
        'timestamp': [1000, 1001],
        'cluster': [0, 0],
        'keep': [True, True]
    })
    
    outliers = pd.DataFrame({
        'lat': [53.60],
        'lon': [10.10],
        'timestamp': [1000],
        'keep': [False]
    })
    
    result = PipelineResult(
        has_path=False,
        filtered=filtered,
        outliers=outliers
    )
    config = PipelineConfig(city="hamburg")
    
    html = render_map(result, config)
    
    assert isinstance(html, str)
    assert len(html) > 500


def test_render_map_empty_result():
    """render_map should handle empty filtered DataFrame."""
    result = PipelineResult(
        has_path=False,
        filtered=pd.DataFrame(),
        outliers=pd.DataFrame()
    )
    config = PipelineConfig(city="hamburg")
    
    html = render_map(result, config)
    
    assert isinstance(html, str)
    assert len(html) > 100  # Should still return valid HTML