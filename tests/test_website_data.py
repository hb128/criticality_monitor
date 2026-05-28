import pandas as pd
import pytest
from zoneinfo import ZoneInfo
from cm_modular.website_data import _to_berlin, prepare_city_leaderboard_data, prepare_current_stats


BERLIN = ZoneInfo("Europe/Berlin")
def test_to_berlin_converts_naive_utc():
    result = _to_berlin("2024-06-01 10:00:00")
    assert result is not None
    assert result.tzinfo is not None
    assert result.tzinfo.key == "Europe/Berlin"

def test_to_berlin_handles_nat():
    assert _to_berlin(pd.NaT) is None

def test_to_berlin_handles_aware_non_berlin():
    import datetime
    dt = datetime.datetime(2024, 6, 1, 10, 0, 0, tzinfo=ZoneInfo("UTC"))
    result = _to_berlin(dt)
    # UTC+0 → Berlin CEST = UTC+2, so 10:00 UTC = 12:00 Berlin
    assert result.hour == 12

def test_to_berlin_invalid_input_returns_none():
    assert _to_berlin("not-a-date") is None


def _make_leaderboard_df():
    return pd.DataFrame([
        {"city": "Hamburg",  "length_m": 12000.0, "t": "2024-06-01 20:00:00", "n_filtered": 80},
        {"city": "Hamburg",  "length_m": 9000.0,  "t": "2024-05-01 20:00:00", "n_filtered": 60},
        {"city": "Berlin",   "length_m": 15000.0, "t": "2024-06-01 19:00:00", "n_filtered": 100},
    ])

def test_leaderboard_returns_top_n_by_length():
    result = prepare_city_leaderboard_data(_make_leaderboard_df(), limit=1)
    assert len(result["records"]) == 1
    assert result["records"][0]["city"] == "Berlin"  # Berlin hat 15 km > Hamburg 12 km

def test_leaderboard_deduplicates_by_latest_timestamp():
    result = prepare_city_leaderboard_data(_make_leaderboard_df())
    # Hamburg darf nur einmal auftauchen
    cities = [r["city"] for r in result["records"]]
    assert cities.count("Hamburg") == 1

def test_leaderboard_uses_latest_not_max_length():
    # Hamburg: neuster Eintrag hat 12 km, älterer hat 9 km → 12 km erwartet
    result = prepare_city_leaderboard_data(_make_leaderboard_df())
    hh = next(r for r in result["records"] if r["city"] == "Hamburg")
    assert hh["length_m"] == 12000.0

def test_leaderboard_empty_df_returns_empty_records():
    assert prepare_city_leaderboard_data(pd.DataFrame()) == {"records": []}


def _make_stats_df():
    return pd.DataFrame([
        {"city": "Hamburg", "length_m": 12000.0, "t": "2024-06-01 20:00:00", "n_filtered": 80},
        {"city": "Berlin",  "length_m": 15000.0, "t": "2024-06-01 19:00:00", "n_filtered": 100},
    ])

def test_current_stats_uses_hamburg_only():
    result = prepare_current_stats(_make_stats_df())
    # max_length muss 12000, nicht 15000 sein
    assert result["max_length"] == 12000.0

def test_current_stats_case_insensitive():
    df = pd.DataFrame([
        {"city": "HAMBURG", "length_m": 5000.0, "t": "2024-06-01 20:00:00", "n_filtered": 30},
    ])
    result = prepare_current_stats(df)
    assert result["latest_length"] == 5000.0

def test_current_stats_empty_returns_defaults():
    result = prepare_current_stats(pd.DataFrame())
    assert result["n_filtered"] == 0
    assert result["latest_date"] == "No data"

from cm_modular.website_data import prepare_plot_data

# --- _to_berlin: Zeile 32 ---
# pd.to_datetime(..., utc=True) gibt immer tz-aware zurück — der Branch
# ist im Produktionscode dead code. Trotzdem Coverage erzwingen via Mock:
def test_to_berlin_tz_localize_fallback(monkeypatch):
    import cm_modular.website_data as wd
    import pandas as pd
    original = pd.to_datetime

    def patched(val, utc):
        ts = original(val, utc=utc)
        # Simuliere einen Timestamp ohne tzinfo
        return ts.tz_localize(None)

    monkeypatch.setattr(pd, "to_datetime", patched)
    result = wd._to_berlin("2024-06-01 10:00:00")
    assert result is not None


# --- Leaderboard: Zeile 49 ---
def test_leaderboard_all_nan_timestamps_uses_fallback():
    df = pd.DataFrame([
        {"city": "Hamburg", "length_m": 5000.0, "t": pd.NaT, "n_filtered": 40},
    ])
    result = prepare_city_leaderboard_data(df)
    assert len(result["records"]) == 1
    assert result["records"][0]["length_m"] == 5000.0


# --- Leaderboard: Zeilen 57–59 ---
def test_leaderboard_invalid_timestamp_yields_unknown_date(monkeypatch):
    import cm_modular.website_data as wd
    monkeypatch.setattr(wd, "_to_berlin", lambda x: None)
    df = pd.DataFrame([
        {"city": "Hamburg", "length_m": 5000.0, "t": "2024-06-01 20:00:00", "n_filtered": 40},
    ])
    result = wd.prepare_city_leaderboard_data(df)
    assert result["records"][0]["date"] == "Unknown"


# --- prepare_current_stats: Zeile 96 ---
def test_current_stats_no_city_column_returns_defaults():
    df = pd.DataFrame([{"length_m": 5000.0, "n_filtered": 40}])
    result = prepare_current_stats(df)
    assert result["n_filtered"] == 0
    assert result["latest_date"] == "No data"


# --- prepare_plot_data: Zeilen 129–165 ---
def test_plot_data_empty_df_returns_empty():
    result = prepare_plot_data(pd.DataFrame(), [], 120)
    assert result == {"x": [], "y": [], "links": [], "cities": []}

def test_plot_data_no_t_column_returns_empty():
    df = pd.DataFrame([{"length_m": 5000.0}])
    result = prepare_plot_data(df, ["link1"], 120)
    assert result == {"x": [], "y": [], "links": [], "cities": []}

def test_plot_data_all_nan_timestamps_returns_empty_lists():
    df = pd.DataFrame([{"t": pd.NaT, "length_m": 5000.0, "city": "Hamburg"}])
    result = prepare_plot_data(df, ["link1"], 120)
    # valid_df ist leer → filtered_links=[], cities=[], reorder-Branch nicht betreten
    assert result["x"] == []

def test_plot_data_hamburg_sorted_last():
    df = pd.DataFrame([
        {"t": "2024-06-01 19:00:00", "length_m": 8000.0, "city": "Berlin"},
        {"t": "2024-06-01 20:00:00", "length_m": 12000.0, "city": "Hamburg"},
    ])
    result = prepare_plot_data(df, ["link_berlin", "link_hh"], 120)
    assert result["cities"][-1] == "Hamburg"

def test_plot_data_max_minutes_cuts_old_entries():
    df = pd.DataFrame([
        {"t": "2024-06-01 10:00:00", "length_m": 5000.0, "city": "Hamburg"},
        {"t": "2024-06-01 20:00:00", "length_m": 12000.0, "city": "Hamburg"},
    ])
    # max_minutes_plot=60 → nur Einträge ab 19:00 UTC
    result = prepare_plot_data(df, ["old", "new"], max_minutes_plot=60)
    assert len(result["x"]) == 1
    assert result["y"][0] == 12000.0

def test_plot_data_timestamps_are_berlin_iso():
    df = pd.DataFrame([
        {"t": "2024-06-01 20:00:00", "length_m": 12000.0, "city": "Hamburg"},
    ])
    result = prepare_plot_data(df, ["link"], 120)
    assert "+02:00" in result["x"][0]  # CEST = UTC+2