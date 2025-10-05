#!/usr/bin/env python3
"""
Render a local HTML file to a PNG and create a simple wrapper HTML that embeds the PNG.

Requires:
    pip install playwright
    python -m playwright install

Usage:
    python render_and_wrap.py path/to/input.html --out outdir
    python render_and_wrap.py path/to/input.html --out outdir --width 768 --height 1024 --dpr 2 --fullpage
"""
import argparse
import pathlib
import sys
import time
from typing import Optional

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    print("Playwright is not installed or not available.")
    print("Install with: pip install playwright")
    print("Then install browsers: python -m playwright install")
    raise

def render_html_to_png(input_html: pathlib.Path, out_dir: pathlib.Path,
                       width: int, height: int, dpr: int,
                       full_page: bool, wait_for: str ,
                       user_agent: str, timeout: int,
                       wrapper_name: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = out_dir / "screenshot.png"
    # Allow custom naming of wrapper (default remains ipad.html)
    wrapper_path = out_dir / wrapper_name

    # Resolve file:// URL for local file loading
    url = input_html.resolve().as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context_args = {
            "viewport": {"width": width, "height": height},
            "device_scale_factor": dpr,
            # is_mobile False by default; can be changed if you need mobile UA/behavior
        }
        if user_agent:
            context_args["user_agent"] = user_agent

        context = browser.new_context(**context_args)
        page = context.new_page()

        print(f"Opening {url} with viewport {width}x{height} @ dpr {dpr} ...")
        page.goto(url, wait_until="networkidle", timeout=timeout)

        if wait_for:
            print(f"Waiting for selector {wait_for} ...")
            page.wait_for_selector(wait_for, timeout=timeout)

        # Small sleep sometimes helps with fonts / rendering (adjust if needed)
        time.sleep(0.2)

        page.screenshot(path=str(screenshot_path), full_page=full_page)
        print(f"Saved screenshot: {screenshot_path} ({'full page' if full_page else 'viewport'})")

        # Create a simple wrapper HTML that references the PNG
        wrapper_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>Rendered screenshot</title>
  <style>
    html,body{{height:100%;margin:0;background:#fff;}}
    .wrap{{display:flex;align-items:center;justify-content:center;height:100%;}}
    img{{max-width:100%;height:auto;display:block}}
  </style>
</head>
<body>
  <div class="wrap">
    <img src="{screenshot_path.name}" alt="Rendered screenshot">
  </div>
</body>
</html>
"""
    wrapper_path.write_text(wrapper_html, encoding="utf-8")
    print(f"Saved wrapper HTML: {wrapper_path}")


    return screenshot_path, wrapper_path

def watch_and_render(input_path: pathlib.Path, *,
                     render_kwargs: dict,
                     interval: float = 5.0,
                     settle: float = 0.2,
                     quiet: bool = False):
    """Watch the given file; when it appears or changes, re-render.

    Parameters:
        input_path: Path to HTML file to watch.
        render_kwargs: kwargs passed to render_html_to_png (excluding input/out_dir)
        interval: seconds between polling checks
        settle: delay after detecting modification before reading (lets writer finish)
        quiet: reduce logging noise
    """
    last_mtime: Optional[float] = None
    last_result = None
    printed_waiting = False
    try:
        while True:
            if not input_path.exists():
                if not printed_waiting and not quiet:
                    print(f"[watch] Waiting for file to appear: {input_path}")
                    printed_waiting = True
                time.sleep(interval)
                continue
            printed_waiting = False
            try:
                mtime = input_path.stat().st_mtime
            except FileNotFoundError:
                # Race: file removed between exists() and stat()
                time.sleep(interval)
                continue

            if last_mtime is None or mtime > last_mtime + 1e-6:
                if not quiet:
                    if last_mtime is None:
                        print(f"[watch] Detected initial file. Rendering {input_path} ...")
                    else:
                        print(f"[watch] Change detected (mtime {mtime}); re-rendering ...")
                time.sleep(settle)  # allow writer to finish
                try:
                    screenshot, wrapper = render_html_to_png(
                        input_html=input_path,
                        **render_kwargs
                    )
                    last_result = (screenshot, wrapper)
                    last_mtime = mtime
                    if not quiet:
                        print(f"[watch] Render complete @ {time.strftime('%H:%M:%S')} -> {wrapper}")
                except Exception as e:
                    print(f"[watch] Render failed: {e}")
                    # keep last_mtime so we'll retry upon *next* modification
            time.sleep(interval)
    except KeyboardInterrupt:
        if not quiet:
            print("\n[watch] Stopped by user (Ctrl+C)")
    return last_result

def main():
    p = argparse.ArgumentParser(description="Render HTML -> PNG and generate simple HTML wrapper.")
    p.add_argument("input", help="Path to input HTML file (will be watched if --watch is used)")
    p.add_argument("--out", "-o", default="data/sites", help="Output directory (will be created) (default: %(default)s)")
    p.add_argument("--width", type=int, default=1024, help="CSS viewport width (default: %(default)s, iPad3 logical width)")
    p.add_argument("--height", type=int, default=768, help="CSS viewport height (default: %(default)s)")
    p.add_argument("--dpr", type=int, default=2, help="devicePixelRatio (default: %(default)s for Retina)")
    p.add_argument("--fullpage", action="store_true", help="Capture full page (may produce a tall image)")
    p.add_argument("--wait-for", help="Optional CSS selector to wait for before screenshot")
    p.add_argument("--user-agent", help="Override user agent string")
    p.add_argument("--timeout", type=int, default=30000, help="Navigation timeout in ms (default: %(default)s)")
    p.add_argument("--wrapper-name", default="ipad.html", help="Filename for generated wrapper HTML (default: %(default)s)")
    p.add_argument("--watch", action="store_true", help="Continuously watch the input file and re-render on changes")
    p.add_argument("--interval", type=float, default=5.0, help="Polling interval seconds for watch mode (default: %(default)s)")
    p.add_argument("--settle", type=float, default=0.2, help="Settling delay seconds after change detected before rendering (default: %(default)s)")
    p.add_argument("--quiet", action="store_true", help="Reduce log verbosity in watch mode")
    args = p.parse_args()
    input_path = pathlib.Path(args.input)
    out_dir = pathlib.Path(args.out)

    render_kwargs = dict(
        out_dir=out_dir,
        width=args.width,
        height=args.height,
        dpr=args.dpr,
        full_page=args.fullpage,
        wait_for=args.wait_for,
        user_agent=args.user_agent,
        timeout=args.timeout,
        wrapper_name=args.wrapper_name,
    )

    if args.watch:
        # In watch mode we don't bail out if file is missing initially.
        print(f"[watch] Starting watch on {input_path} (interval={args.interval}s)")
        watch_and_render(
            input_path,
            render_kwargs=render_kwargs,
            interval=args.interval,
            settle=args.settle,
            quiet=args.quiet,
        )
        return

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(2)

    print("Rendering...")
    screenshot, wrapper = render_html_to_png(
        input_html=input_path,
        **render_kwargs
    )
    print("Done.")

if __name__ == "__main__":
    main()