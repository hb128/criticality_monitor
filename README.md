# Criticality Monitor

The Criticality Monitor ingests live (or archived) rider positions from Critical Maps (https://www.criticalmaps.net/map):
1. Filters and clusters raw GPS points into stable spatial clusters
2. Builds a geometric graph over cluster centroids with configurable edge penalties
3. Computes an angle‑aware (turn + step + long/short edge) shortest path using an expanded‑state Dijkstra
4. Renders an interactive HTML map (true geometric path length shown; penalties only guide selection)
5. (Optionally) Automates a watch → process → static site rebuild chain for near‑real‑time publishing

## Why
CMs are fun.

## Core Features
- Robust k‑NN + MAD outlier filtering
- Cluster formation and centroid graph construction
- Long‑edge (L0) penalty + short‑edge floor
- Turn + step penalties via expanded state (heading memory)
- Clear separation: penalized cost vs displayed geometric distance
- Modular pipeline (extend or swap stages)
- Continuous directory watcher + lightweight static site build

## High Level Pipeline
Raw Log → Parse → Filter → Cluster → Graph Build (+ penalties) → Path Search → Map Render → (Site Integration)

## Install
```bash
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install  # Install browser for Playwright
```

## Quick Start (Single File → Map)
```bash
python -m cm_modular.scripts.build_map path/to/input_log.txt --out route_map.html
```
Python API:
```python
from cm_modular.pipeline import Pipeline, PipelineConfig
pipe = Pipeline(PipelineConfig())
m, out_path = pipe.run("path/to/input_log.txt", "route_map.html")
```

## Automated Chain (Live-ish Workflow)
1. Logging (ingest / copy new raw dumps):
```bash
python -m scripts.logger --log-dir test_deployment/logs --debug-source ./cm_logs/20220624/
```
2. Processing (cluster, path, map) on interval:
```bash
python -m scripts.watch_and_process --interval 1 --watch-dir test_deployment/logs/ --output-dir test_deployment --city Hamburg
```
3. Site rebuild:
```bash
python -m scripts.watch_and_build_site --site-root ./test_deployment/
```

## Configuration
Use PipelineConfig (see cm_modular/pipeline.py) or corresponding CLI flags:
- kNN size / MAD threshold
- Long edge penalty factor
- Step penalty, turn penalty, short‑edge minimum
- Output paths / caching toggles
View CLI options:
```bash
python -m cm_modular.scripts.build_map --help
```

## Directory (Essentials)
- cm_modular/ : library (pipeline + algorithms)
- scripts/ : primary CLI entry points

## Testing
```bash
pytest -q
```

## Disclaimer
This project is not officially affiliated with Critical Maps.
