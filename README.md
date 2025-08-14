# cm_modular

Modularized version of the *Clusters map with angle-biased path* script.  
It splits the original monolithic code into small classes with clear responsibilities and docstrings.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

### CLI
```bash
python -m cm_modular.scripts.build_map /path/to/20220624_221210.txt --out hamburg_clusters_with_path_angle.html
```
or directly:
```bash
python scripts/build_map.py /path/to/20220624_221210.txt --out hamburg_clusters_with_path_angle.html
```

### Python API
```python
from cm_modular.pipeline import Pipeline, PipelineConfig
pipe = Pipeline(PipelineConfig())
m, out_path = pipe.run("/path/to/20220624_221210.txt", "hamburg_clusters_with_path_angle.html")
```

## Notes

- The algorithm is unchanged from your script:
  - Robust k-NN filtering (MAD-thresholded)
  - Graph construction with a long-edge penalty (L0, penalty_factor)
  - Angle-biased expanded-state Dijkstra (turn + step penalties + short-edge floor)
  - True geometric path length is shown on the map (penalties do **not** affect displayed length).
- All constants are configurable via `PipelineConfig` or CLI flags.
- Bounding box defaults to Hamburg (53.3..53.8 / 9.6..10.35) and can be overridden.
