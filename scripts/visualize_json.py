from pathlib import Path
from cm_modular.pipeline import PipelineConfig, Pipeline
from cm_modular.rendering import render_map


def visualize_json(json_path: str, city: str = "hamburg") -> None:
    json_path = Path(json_path)
    out_html = json_path.with_suffix(".html")

    config = PipelineConfig(city=city)
    p = Pipeline(config)
    p.add_files([str(json_path)])

    # Run pipeline (pure computation, no IO)
    result = p.run()
    
    # Render and write HTML (script layer handles IO)
    html = render_map(result, config)
    out_html.write_text(html, encoding='utf-8')

    print(f"Wrote map to {out_html}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("json_path", help="Path to Critical Maps JSON log")
    parser.add_argument("--city", default="hamburg")
    args = parser.parse_args()

    visualize_json(args.json_path, city=args.city)