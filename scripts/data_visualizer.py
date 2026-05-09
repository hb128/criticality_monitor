# app_sqlite.py
import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import pydeck as pdk
import streamlit as st

# ---------- Load from SQLite ----------
@st.cache_data
def load_data_from_sqlite(path: str, table: str = "positions"):
    # path: path to your .db / .sqlite file
    con = sqlite3.connect(path)
    try:
        query = f"SELECT device_id, timestamp, lat, lon FROM {table}"
        df = pd.read_sql_query(query, con)   # returns a DataFrame
    finally:
        con.close()

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df.sort_values("timestamp")
    return df

DB_PATH = "data/cm_202511.db"   # change to your sqlite file
TABLE_NAME = "positions"   # change if needed

df = load_data_from_sqlite(DB_PATH, TABLE_NAME)

min_t = df["timestamp"].min()
max_t = df["timestamp"].max()

min_t = df["timestamp"].min()
max_t = df["timestamp"].max()

# ---------- Sidebar controls ----------

st.set_page_config(layout="wide")

st.sidebar.header("Controls")
st.sidebar.write("Time slider selects the current time; "
                 "points from now back 10 minutes are shown.")

# --- initialise session state once ---
if "current_time" not in st.session_state:
    st.session_state.current_time = max_t.to_pydatetime()

# --- slider using session_state key ---
# --- time controls row ---
left_btn, center_slider, right_btn = st.columns([1, 6, 1])

# initialize state once
if "current_time" not in st.session_state:
    st.session_state.current_time = max_t.to_pydatetime()

def shift_time(delta_minutes: int):
    st.session_state.current_time += timedelta(minutes=delta_minutes)

with left_btn:
    st.button("← -1 min", on_click=shift_time, kwargs={"delta_minutes": -1})

with right_btn:
    st.button("+1 min →", on_click=shift_time, kwargs={"delta_minutes": +1})

with center_slider:
    current_time = st.slider(
        "Current time",
        min_value=min_t.to_pydatetime(),
        max_value=max_t.to_pydatetime(),
        format="YYYY-MM-DD HH:mm:ss",
        key="current_time",
        step=timedelta(minutes=1),
    )


window = timedelta(minutes=10)
t_start = current_time - window

mask = (df["timestamp"] >= t_start) & (df["timestamp"] <= current_time)
df_win = df.loc[mask].copy()


# if df_win.empty:
#     st.write("No points in the selected time window.")
#     st.stop()

# st.write("Points in selected time window:", len(df_win))

df_win["age_norm"] = (
    (df_win["timestamp"] - t_start) / (current_time - t_start)
).clip(0, 1)

# mark newest point per device (latest timestamp)
df_win["is_first"] = (
    df_win.sort_values("timestamp", ascending=False)
          .groupby("device_id")
          .cumcount() == 0
)

# deterministic color per device
unique_ids = df_win["device_id"].unique()


bright_colors = [
    (255, 69, 0),     # orange-red
    (50, 205, 50),    # lime green
    (30, 144, 255),   # dodger blue
    (255, 215, 0),    # gold
    (218, 112, 214),  # orchid
    (0, 255, 255),    # cyan
    (255, 105, 180),  # hot pink
    (173, 255, 47),   # green-yellow
    (255, 140, 0),    # dark orange
    (0, 191, 255),    # deep sky blue
]

color_map = {}
for i, did in enumerate(unique_ids):
    base = bright_colors[hash(did) % len(bright_colors)]
    color_map[did] = base


def fade_color(base_rgb, age_norm):
    alpha = int(20 + 225 * age_norm)
    return [*base_rgb, alpha]

df_win["color"] = df_win.apply(
    lambda r: fade_color(color_map[r["device_id"]], r["age_norm"]), axis=1
)
df_win["radius"] = df_win.apply(
    lambda r:  10 if (r["is_first"] and r['age_norm'] > 0.9) else 3, axis=1
)

scatter_layer = pdk.Layer(
    "ScatterplotLayer",
    data=df_win,
    get_position="[lon, lat]",
    get_fill_color="color",
    get_radius="radius",
    pickable=True,
)

paths = (
    df_win.sort_values(["device_id", "timestamp"])
          .groupby("device_id")[["lon", "lat"]]
          .apply(lambda g: g.values.tolist())
          .reset_index(name="path")
)

paths["color"] = paths["device_id"].map(color_map).apply(
    lambda c: [c[0], c[1], c[2], 120]
)

path_layer = pdk.Layer(
    "PathLayer",
    data=paths,
    get_path="path",
    get_color="color",
    width_scale=1,
    width_min_pixels=4,
    rounded=True,
    pickable=False,
)

deck = pdk.Deck(
    map_provider="carto",
    map_style="dark",
    initial_view_state=pdk.ViewState(
        latitude=53.65,
        longitude=10.0,
        zoom=12,
        pitch=0,
    ),
    layers=[path_layer, scatter_layer],
    tooltip={"text": "ID: {device_id}\nTime: {timestamp}"},
)

st.pydeck_chart(deck, height=700)
