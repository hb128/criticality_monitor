# Stage Contracts

> Goal: Document the *current* behaviour of each pipeline stage so it can be tested and refactored independently, without changing algorithms.

Each contract specifies:

- Inputs (types, shapes, required columns)
- Outputs (types, shapes, added columns)
- Invariants and edge‑case behaviour

These contracts are descriptive, not prescriptive: they describe what the current code does.

---

## io.py – DataLoader

### DataLoader.load_locations_json(path)

- **Input**  
  - `path: str`  
    - Filesystem path to a JSON file in the Critical Maps API format.  
    - Expected keys:  
      - Top‑level `locations: dict[str, object]`.  
      - Each entry:  
        - `latitude: int` (micro‑degrees, WGS84)  
        - `longitude: int` (micro‑degrees, WGS84)  
        - `timestamp: int | float | None` (Unix‑like)
- **Output**  
  - `pd.DataFrame` with columns:  
    - `id: str` – key from `locations` dict.  
    - `lat: float` – degrees, computed as `latitude / 1_000_000`.  
    - `lon: float` – degrees, computed as `longitude / 1_000_000`.  
    - `timestamp: int | float | None` – copied from JSON.
- **Invariants**  
  - One row per original location.  
  - No additional columns are added.  
  - Index is not semantically meaningful; callers must not rely on it.

### DataLoader.load_multiple_locations_json(paths)

- **Input**  
  - `paths: list[str]` – list of JSON file paths.  
- **Output**  
  - `pd.DataFrame` with the same columns as `load_locations_json`.  
- **Invariants**  
  - Vertically concatenates per‑file results.  
  - Sorted by `id`, then `timestamp` ascending.  
  - Index reset to a `RangeIndex` from `0` to `len(df) - 1`.

---

## filtering.py – DataFilter and RobustKNNFilter

### DataFilter.bbox(df, lat_min, lat_max, lon_min, lon_max)

- **Input**  
  - `df: pd.DataFrame` with at least `lat: float`, `lon: float`.  
  - `lat_min, lat_max, lon_min, lon_max: float` – inclusive bounds.
- **Output**  
  - New `pd.DataFrame` containing only rows inside the bounding box.  
- **Invariants**  
  - All returned rows satisfy  
    - `lat_min ≤ lat ≤ lat_max`  
    - `lon_min ≤ lon ≤ lon_max`.  
  - Index is reset; original index is discarded.  
  - No new columns are introduced.

### RobustKNNFilter.keep_by_knn(D, k, nsigmas)

- **Input**  
  - `D: np.ndarray[float]` with shape `(n, n)` – dense pairwise distance matrix in metres.  
  - `k: int` – neighbour index used for isolation measure.  
  - `nsigmas: float` – MAD threshold multiplier.
- **Output**  
  - `keep: np.ndarray[bool]` with shape `(n,)` – True for inliers, False for outliers.  
  - `kmed: float` – median `k`‑th neighbour distance.  
- **Invariants and behaviour**  
  - `D` is treated as symmetric and non‑negative; diagonal entries are assumed to be 0.  
  - For each point `i`,  
    - `kth_dist[i]` is the `k`‑th smallest value in row `i` (excluding or including self consistently with implementation).  
    - `median = median(kth_dist)`  
    - `mad = median(|kth_dist – median|)`  
    - `threshold = median + nsigmas * mad`  
    - Hard minimum: `threshold = max(30.0, threshold)`  
  - If `mad == 0`, a fallback path is used that does **not** crash and uses a fixed median scale (~50 m) instead of collapsing the threshold.  
  - Points with `kth_dist[i] > threshold` are marked as outliers (`keep[i] == False`).  
  - `keep` and `kmed` are aligned with the ordering of rows/cols in `D`.

---

## geo.py – GeoUtils

### GeoUtils.deg2meters(lat, lon, lat0=None, lon0=None)

- **Input**  
  - `lat: np.ndarray[float]` – latitudes in degrees.  
  - `lon: np.ndarray[float]` – longitudes in degrees.  
  - `lat0: float | None`, `lon0: float | None` – reference point in degrees.  
- **Output**  
  - `x: np.ndarray[float]`, `y: np.ndarray[float]` – planar coordinates in metres using equirectangular WGS84 approximation.  
- **Invariants and behaviour**  
  - If `lat0` or `lon0` are `None`, they are set to the median of `lat` and `lon` respectively.  
  - Uses Earth radius `R ≈ 6_371_000` m.  
  - Valid for city‑scale extents (order 10 km), not for national‑scale bounding boxes.  
  - Shapes of `x` and `y` match the input shape.

### GeoUtils.pairwise_xy(X, Y)

- **Input**  
  - `X: np.ndarray[float]` – x coordinates in metres, shape `(n,)` or `(n, 1)`.  
  - `Y: np.ndarray[float]` – y coordinates in metres, same length as `X`.  
- **Output**  
  - `D: np.ndarray[float]` with shape `(n, n)` – dense Euclidean distance matrix.  
- **Invariants and behaviour**  
  - `D` is symmetric: `D[i, j] == D[j, i]` for all `i, j`.  
  - Diagonal entries are zero: `D[i, i] == 0.0`.  
  - Implementation is a pure‑Python `O(n²)` loop; memory usage is `O(n²)` (`n=1000` → ~8 MB).  
  - Performance degrades noticeably for `n > 2000` points.

---

## graphing.py – GraphBuilder

### GraphBuilder.build_graph(D, kmed, L0, penalty_factor)

- **Input**  
  - `D: np.ndarray[float]` with shape `(n, n)` – pairwise distances in metres.  
  - `kmed: float` – median neighbour distance from KNN stage.  
  - `L0: float` – length threshold in metres.  
  - `penalty_factor: float` – cost weight beyond `L0`.  
- **Output**  
  - `adj: list[list[tuple[int, float]]]` – adjacency list.  
  - `radius_m: float` – connection radius actually used.  
- **Invariants and behaviour**  
  - Connection radius computed as `r = clip(1.6 * kmed, 30.0, 300.0)`.  
  - For each `i` and `j` with `i != j` and `D[i, j] ≤ r`:  
    - Edge cost: `cost = D[i, j] + penalty_factor * max(0, D[i, j] - L0)`.  
    - `(j, cost)` is appended to `adj[i]` and `(i, cost)` to `adj[j]` (undirected graph).  
  - No self‑loops: `adj[i]` never contains `i`.  
  - `len(adj) == n`; every node appears as a key, even if isolated (may have an empty neighbour list).

### GraphBuilder.angle_bias_for_segment(xf, yf, path_indices, i)

- **Input**  
  - `xf, yf: np.ndarray[float]` – planar coordinates of all nodes.  
  - `path_indices: list[int]` – node indices along a path.  
  - `i: int` – segment index (0‑based).  
- **Output**  
  - `factor: float` – multiplicative factor for segment `i`.  
- **Invariants and behaviour**  
  - For the first segment (`i == 0`), returns `1.0`.  
  - For `i > 0`, returns a value ≥ 1.0 increasing with the turn angle at that node.  
  - Used to populate `segmentmetrics` in `Pipeline.compute`; does not affect routing decisions directly.

### GraphBuilder.components(adj)  (legacy)

- **Status**  
  - DFS‑based connected components over `adj`.  
  - Functionally duplicates `Clusterer.assign_from_components` and is scheduled for removal (Phase 2).  
- **Contract (current)**  
  - Input: `adj` as above.  
  - Output: `comps: list[list[int]]`, each a list of node indices in a component.  
  - Components are disjoint and cover all node indices present in `adj`.

---

## clustering.py – Clusterer

### Clusterer.assign_from_components(adj)

- **Input**  
  - `adj: list[list[tuple[int, float]]]` – adjacency list representing an undirected graph.  
- **Output**  
  - `comps: list[list[int]]` – one list of node indices per component (DFS order).  
  - `sizes: list[int]` – number of nodes in each component.  
  - `order: list[int]` – component indices sorted by size descending.  
  - `cluster_id: np.ndarray[int]` with shape `(n,)` – per‑node cluster rank.  
- **Invariants and behaviour**  
  - Each node appears in exactly one component.  
  - `cluster_id[i] == 0` for nodes in the largest component, `1` for the second largest, etc.  
  - Isolated nodes form components of size 1 with appropriate rank.  
  - Callers add a `cluster: int` column to the DataFrame using `cluster_id`.

---

## routing.py – AngleBiasedRouter and helpers

### AngleBiasedRouter (constructor and parameters)

- **Inputs at construction**  
  - `X, Y: np.ndarray[float]` – planar coordinates of all nodes.  
  - `angle_bias_m_per_rad: float` – turn‑penalty weight.  
  - `step_penalty_m: float` – flat cost per edge.  
  - `min_edge_cost_m: float` – minimum effective edge cost.  
- **Purpose**  
  - Implements expanded‑state Dijkstra over `(previous_node, current_node)` so that turn angles influence cost.

### dijkstra(adj, src)

- **Input**  
  - `adj: list[list[tuple[int, float]]]` – adjacency list with penalised edge costs.  
  - `src: int` – start node index.  
- **Output**  
  - `best_dist_to: dict[tuple[int, int], float]` – cost per expanded state `(prev, u)`.  
  - `prev_state: dict[tuple[int, int], tuple[int, int]]` – backpointers for each state.  
  - `best_last_prev: dict[int, int]` – best predecessor for each end node.  
- **Invariants and behaviour**  
  - Edge transition cost is  
    - `raw = max(w_uv, min_edge_cost_m)` where `w_uv` is the edge weight from `adj`.  
    - `angle_cost = angle_bias_m_per_rad * turn_angle(p, u, v)` using absolute heading change.  
    - `total_cost = raw + step_penalty_m + angle_cost`.  
  - First step from `src` uses `turn_angle == 0`.

### dijkstra_plain(adj, src)

- **Input/Output**  
  - Standard Dijkstra over `adj`.  
  - Returns `dist: np.ndarray[float]`, `prev: np.ndarray[int]` using edge weights as‑is (no angle penalties).  

### as_geometric_adjacency(adj, D_base)

- **Input**  
  - `adj: list[list[tuple[int, float]]]` – original adjacency list.  
  - `D_base: np.ndarray[float]` – base distance matrix.  
- **Output**  
  - New adjacency list with identical neighbours but weights replaced by `D_base[i, j]`.  

### reconstruct_path(prev_state, end_node, last_prev)

- **Input**  
  - `prev_state: dict[tuple[int, int], tuple[int, int]]`.  
  - `end_node: int`.  
  - `last_prev: int`.  
- **Output**  
  - `path_indices: list[int]` – node indices from source to `end_node` inclusive.  

### path_true_length_m(D_base, path_indices)

- **Input**  
  - `D_base: np.ndarray[float]` – base distance matrix.  
  - `path_indices: list[int]`.  
- **Output**  
  - `length_m: float` – geometric (unpenalised) length of the path.  

### Diameter‑finding heuristic (used in Pipeline)

- **Strategy**  
  1. `adj_geom = as_geometric_adjacency(adj, D_f)` using geometric distances.  
  2. `dijkstra_plain(adj_geom, s0)` from an arbitrary start → farthest node `a`.  
  3. `dijkstra_plain(adj_geom, a)` → farthest node `b` (diameter endpoints).  
  4. `dijkstra(adj, a)` on original penalised `adj`.  
  5. `path_indices = reconstruct_path(prev_a, b, best_prev_ab)`.  
  6. `length_m = path_true_length_m(D_f, path_indices)`; this is the reported route length.

---

## Time‑window cuts inside pipeline.py

These are currently inline in `Pipeline.compute` but planned to be extracted into named functions in later phases.

### Clustering timespan cut

- **Input**  
  - `df: pd.DataFrame` with at least `timestamp` and spatial columns.  
  - `clustering_timespans: float | None` (seconds).  
- **Behaviour**  
  - If `clustering_timespans is None`, `df` is left unchanged.  
  - Otherwise, only rows within the trailing `clustering_timespans` seconds of the latest timestamp are kept for clustering.

### Path‑endpoint timespan cut

- **Input**  
  - `df: pd.DataFrame` with `cluster` and `timestamp` columns.  
  - `pathtimespans: float | None` (seconds).  
- **Behaviour**  
  - Cluster `0` is treated as the main cluster.  
  - If `pathtimespans is None`, all cluster‑0 rows are considered when selecting path endpoints.  
  - Otherwise, only cluster‑0 rows within the trailing `pathtimespans` seconds are used.