from pathlib import Path
from cm_modular.pipeline import PipelineConfig, Pipeline


def visualize_json(json_path: str, city: str = "hamburg") -> None:
    json_path = Path(json_path)
    out_html = json_path.with_suffix(".html")

    config = PipelineConfig(city=city)
    p = Pipeline(config)
    p.add_files([str(json_path)])

    # This will run the full pipeline and save a Folium map to out_html
    p.run(out_html=str(out_html), return_metrics=False)

    print(f"Wrote map to {out_html}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", help="Path to Critical Maps JSON log")
    parser.add_argument("--city", default="hamburg")
    args = parser.parse_args()

    visualize_json(args.json_path, city=args.city)