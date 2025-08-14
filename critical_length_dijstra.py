# Clusters map with angle-biased path (turns slightly more costly)
import json, math, heapq
from pathlib import Path
import numpy as np
import pandas as pd
import folium

FILE = Path("cm_logs/20220624/20220624_221210.txt")
assert FILE.exists(), f"File not found: {FILE}"

# --- helpers (base) ---
def deg2meters(lat, lon, lat0=None, lon0=None):
    if lat0 is None: lat0 = np.median(lat)
    if lon0 is None: lon0 = np.median(lon)
    R = 6371000.0
    x = np.deg2rad(lon - lon0) * R * np.cos(np.deg2rad(lat0))
    y = np.deg2rad(lat - lat0) * R
    return x, y

def pairwise_xy(X, Y):
    P = np.column_stack([X, Y])
    n = len(P)
    D = np.empty((n,n), dtype=float)
    for i in range(n):
        dx = P[:,0] - P[i,0]
        dy = P[:,1] - P[i,1]
        D[i] = np.hypot(dx, dy)
    return D

def robust_keep_by_knn(D, k=4, n_sigmas=3.0):
    kth = np.partition(D, kth=k, axis=1)[:,k]
    med = float(np.median(kth))
    mad = float(np.median(np.abs(kth - med)) * 1.4826)
    thresh = med + (n_sigmas*mad if mad > 0 else 50.0)
    keep = kth <= max(30.0, thresh)
    return keep, med

# def build_graph(D, k_med):
#     r = float(min(200.0, max(30.0, 1.6*k_med)))
#     n = D.shape[0]
#     adj = [[] for _ in range(n)]
#     for i in range(n):
#         for j in range(n):
#             if i != j and D[i,j] <= r:
#                 adj[i].append((j, float(D[i,j])))
#     return adj, r

def build_graph(D, k_med, L0=50.0, penalty_factor=3.0):
    """
    Build adjacency list from distance matrix D with a penalty for long edges.
    
    Parameters
    ----------
    D : ndarray
        Pairwise distance matrix in meters.
    k_med : float
        Median k-NN distance from robust_keep_by_knn (used for r cutoff).
    L0 : float, optional
        Threshold length (meters) after which to apply a penalty.
    penalty_factor : float, optional
        Extra cost per meter beyond L0 (meters of cost per meter length).
    """
    r = float(min(200.0, max(30.0, 1.6*k_med)))  # original radius cutoff
    n = D.shape[0]
    adj = [[] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j and D[i, j] <= r:
                length = float(D[i, j])
                if length > L0:
                    length += penalty_factor * (length - L0)
                adj[i].append((j, length))
    return adj, r

def components(adj):
    n = len(adj)
    seen = [False]*n
    comps = []
    for i in range(n):
        if seen[i]: continue
        stack=[i]; seen[i]=True; nodes=[i]
        while stack:
            u = stack.pop()
            for v,_ in adj[u]:
                if not seen[v]:
                    seen[v]=True; stack.append(v); nodes.append(v)
        comps.append(nodes)
    return comps

# --- angle helpers ---
def heading(i, j, X, Y):
    """Heading angle (radians) from point i -> j in XY meters coordinates."""
    return math.atan2(Y[j] - Y[i], X[j] - X[i])

def turn_angle(p, u, v, X, Y):
    """Smallest absolute turn angle at u when going p->u->v (0..pi)."""
    a1 = heading(p, u, X, Y)
    a2 = heading(u, v, X, Y)
    da = (a2 - a1 + math.pi) % (2*math.pi) - math.pi  # wrap to [-pi, pi]
    return abs(da)

# --- replace your angle Dijkstra with step + floor penalties ---
def dijkstra_with_angle(adj, src, X, Y,
                        angle_bias_m_per_rad=8.0,
                        step_penalty_m=5.0,        # NEW: fixed cost per edge
                        min_edge_cost_m=15.0):      # NEW: floor for very short edges
    """
    Expanded-state Dijkstra on states (u, p) with:
      cost = max(w, min_edge_cost_m)                 # floor short edges
            + step_penalty_m                         # fixed per-edge cost
            + angle_bias_m_per_rad * turn_angle(p,u,v)  # turn cost
    """
    import heapq, math
    n = len(adj)
    INF = 1e30
    dist = {}
    prev_state = {}
    best_dist_to = [INF]*n
    best_last_prev = [-1]*n

    start = (src, -1)
    dist[start] = 0.0
    best_dist_to[src] = 0.0
    pq = [(0.0, src, -1)]

    def turn_angle(p, u, v):
        if p == -1: return 0.0
        a1 = math.atan2(Y[u]-Y[p], X[u]-X[p])
        a2 = math.atan2(Y[v]-Y[u], X[v]-X[u])
        da = (a2 - a1 + math.pi) % (2*math.pi) - math.pi
        return abs(da)

    while pq:
        d,u,p = heapq.heappop(pq)
        state = (u,p)
        if d != dist.get(state, INF): continue
        for v, w in adj[u]:
            base = max(w, min_edge_cost_m)             # floor short edges
            penalty = step_penalty_m + angle_bias_m_per_rad * turn_angle(p,u,v)
            nd = d + base + penalty
            nxt = (v, u)
            if nd < dist.get(nxt, INF) - 1e-9:
                dist[nxt] = nd
                prev_state[nxt] = state
                heapq.heappush(pq, (nd, v, u))
                if nd < best_dist_to[v] - 1e-9:
                    best_dist_to[v] = nd
                    best_last_prev[v] = u
    return best_dist_to, prev_state, best_last_prev

# helper: true (unpenalized) length of a node path, using the base distance matrix
def path_true_length_m(D_base, path):
    if len(path) < 2: 
        return 0.0
    return float(sum(D_base[path[i], path[i+1]] for i in range(len(path)-1)))

def reconstruct_path_from_states(prev_state, end_node, last_prev):
    """Reconstruct path to end_node using prev_state mapping and (end_node, last_prev) state."""
    path_states = []
    cur = (end_node, last_prev)
    while cur in prev_state:
        path_states.append(cur)
        cur = prev_state[cur]
    # Add the initial state (src, -1)
    path_states.append(cur)
    path_states.reverse()
    # Extract node sequence (take the second element's first item, but start with first state's node)
    path_nodes = [path_states[0][0]]
    for st in path_states[1:]:
        path_nodes.append(st[0])
    return path_nodes

# --- parse & filter ---
with FILE.open("r", encoding="utf-8") as f:
    data = json.load(f)

rows = []
for _id, o in data.get("locations", {}).items():
    lat = o.get("latitude"); lon = o.get("longitude")
    if lat is None or lon is None: 
        continue
    rows.append((_id, lat/1e6, lon/1e6))
df = pd.DataFrame(rows, columns=["id","lat","lon"])

hh = df[df.lat.between(53.3, 53.8) & df.lon.between(9.6, 10.35)].copy().reset_index(drop=True)

x, y = deg2meters(hh["lat"].values, hh["lon"].values)
D = pairwise_xy(x, y)
keep, k_med = robust_keep_by_knn(D, k=4, n_sigmas=3.0)
hh["keep"] = keep

filtered = hh[hh["keep"]].copy().reset_index(drop=True)
outliers = hh[~hh["keep"]].copy().reset_index(drop=True)

# --- graph + components (on filtered) ---
x_f, y_f = deg2meters(filtered["lat"].values, filtered["lon"].values)
D_f = pairwise_xy(x_f, y_f)
adj, radius_m = build_graph(D_f, k_med)
comps = components(adj)

# cluster IDs
sizes = [len(c) for c in comps]
order = np.argsort(sizes)[::-1].tolist()  # largest first
cluster_id = np.full(len(filtered), -1, dtype=int)
for rank, comp_idx in enumerate(order):
    for node in comps[comp_idx]:
        cluster_id[node] = rank
filtered["cluster"] = cluster_id

# --- diameter path on largest comp using angle-biased metric ---
angle_bias_m_per_rad = 8.0  # small penalty per radian of turning
diameter_km = 0.0
path_indices = []
start_idx = end_idx = None

if order:
    main = comps[order[0]]
    if len(main) >= 2:
        s0 = main[0]
        dist0, prev0, bestprev0 = dijkstra_with_angle(adj, s0, x_f, y_f, angle_bias_m_per_rad)
        # pick farthest 'a' within main component under angle-biased distance
        a = max(main, key=lambda i: dist0[i])
        dist_a, prev_a, bestprev_a = dijkstra_with_angle(adj, a, x_f, y_f, angle_bias_m_per_rad)
        b = max(main, key=lambda i: dist_a[i])
        diameter_km = dist_a[b] / 1000.0
        path_indices = reconstruct_path_from_states(prev_a, b, bestprev_a[b])
        start_idx, end_idx = a, b

        # NEW: compute true length from the base distances (meters)
        true_len_m = path_true_length_m(D_f, path_indices)
        diameter_km = true_len_m / 1000.0  # <- use this for display

        # (optional) if you want to see how big the penalty made it:
        penalized_cost_km = dist_a[b] / 1000.0
# --- bounds (2x around filtered bbox) ---
lat_min, lat_max = filtered["lat"].min(), filtered["lat"].max()
lon_min, lon_max = filtered["lon"].min(), filtered["lon"].max()
lat_c = (lat_min + lat_max)/2.0
lon_c = (lon_min + lon_max)/2.0
half_lat = (lat_max - lat_min)/2.0
half_lon = (lon_max - lon_min)/2.0
lat_min2 = lat_c - 2*half_lat
lat_max2 = lat_c + 2*half_lat
lon_min2 = lon_c - 2*half_lon
lon_max2 = lon_c + 2*half_lon

# --- colors ---
palette = [
    "#2ecc71",  # largest cluster
    "#1f77b4", "#ff7f0e", "#9467bd", "#8c564b",
    "#e377c2", "#17becf", "#bcbd22", "#d62728", "#7f7f7f"
]
def color_for_cluster(cid):
    if cid < len(palette): return palette[cid]
    return palette[1 + (cid - 1) % (len(palette)-1)]

# --- build map ---
m = folium.Map(location=[lat_c, lon_c], tiles="OpenStreetMap")

# clusters
for _, r in filtered.iterrows():
    folium.CircleMarker(
        location=[r.lat, r.lon],
        radius=4,
        color=color_for_cluster(int(r.cluster)),
        fill=True,
        fill_opacity=0.9,
        weight=1,
        tooltip=f"cluster {int(r.cluster)}"
    ).add_to(m)

# outliers
for _, r in outliers.iterrows():
    folium.CircleMarker(
        location=[r.lat, r.lon],
        radius=4,
        color="#7f8c8d",
        fill=True,
        fill_opacity=0.8,
        weight=1,
        tooltip="outlier"
    ).add_to(m)

# angle-biased diameter path overlay + start/end markers
if path_indices:
    latlons = list(zip(filtered.loc[path_indices, "lat"], filtered.loc[path_indices, "lon"]))
    folium.PolyLine(
        locations=latlons,
        weight=3,
        color="#111111",
        opacity=0.9,
        tooltip=f"Angle-biased diameter ~{diameter_km:.2f} km (bias={angle_bias_m_per_rad} m/rad)"
    ).add_to(m)
    s_lat = filtered.loc[start_idx, "lat"]; s_lon = filtered.loc[start_idx, "lon"]
    e_lat = filtered.loc[end_idx, "lat"];   e_lon = filtered.loc[end_idx, "lon"]
    folium.Marker([s_lat, s_lon], tooltip="Start", icon=folium.Icon(color="green", icon="play")).add_to(m)
    folium.Marker([e_lat, e_lon], tooltip="End", icon=folium.Icon(color="red", icon="stop")).add_to(m)

# legend
largest_size = sizes[order[0]] if order else 0
legend_html = f"""
<div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;
            background: white; padding: 10px 12px; border: 1px solid #ccc;
            border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.2); font-size:12px;">
  <div style="font-weight:600; margin-bottom:6px;">Clusters & Angle-biased Path</div>
  <div><span style="display:inline-block;width:10px;height:10px;background:{palette[0]};border:1px solid #333;margin-right:6px;"></span>largest cluster ({largest_size} pts)</div>
  <div><span style="display:inline-block;width:10px;height:1px;background:#111;margin:0 6px 0 0;display:inline-block;vertical-align:middle;"></span>diameter path ≈ {diameter_km:.2f} km</div>
  <div>turn bias: {angle_bias_m_per_rad} m per rad</div>
  <div><span style="display:inline-block;width:10px;height:10px;background:#7f8c8d;border:1px solid #333;margin-right:6px;"></span>outliers</div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

m.fit_bounds([[lat_min2, lon_min2], [lat_max2, lon_max2]])

out_path = Path("hamburg_clusters_with_path_angle.html")
m.save(str(out_path))

m, f"[Download the map HTML](sandbox:{out_path})"
