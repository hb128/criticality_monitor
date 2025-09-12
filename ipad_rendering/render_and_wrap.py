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

try:
    from playwright.sync_api import sync_playwright
except Exception as e:
    print("Playwright is not installed or not available.")
    print("Install with: pip install playwright")
    print("Then install browsers: python -m playwright install")
    raise

def render_html_to_png(input_html: pathlib.Path, out_dir: pathlib.Path,
                       width: int, height: int, dpr: int,
                       full_page: bool, wait_for: str = None,
                       user_agent: str = None, timeout: int = 30000):
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = out_dir / "screenshot.png"
    wrapper_path = out_dir / "index.html"

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

        browser.close()

    return screenshot_path, wrapper_path

def parse_args():
    p = argparse.ArgumentParser(description="Render HTML -> PNG and generate simple HTML wrapper.")
    p.add_argument("input", help="Path to input HTML file")
    p.add_argument("--out", "-o", default="out", help="Output directory (will be created)")
    p.add_argument("--width", type=int, default=768, help="CSS viewport width (default 768, iPad3 logical width)")
    p.add_argument("--height", type=int, default=1024, help="CSS viewport height (default 1024)")
    p.add_argument("--dpr", type=int, default=2, help="devicePixelRatio (default 2 for Retina)")
    p.add_argument("--fullpage", action="store_true", help="Capture full page (may produce a tall image)")
    p.add_argument("--wait-for", help="Optional CSS selector to wait for before screenshot")
    p.add_argument("--user-agent", help="Override user agent string")
    p.add_argument("--timeout", type=int, default=30000, help="Navigation timeout in ms")
    return p.parse_args()

def main():
    args = parse_args()
    input_path = pathlib.Path(args.input)
    out_dir = pathlib.Path(args.out)

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}")
        sys.exit(2)

    print("Rendering...")
    screenshot, wrapper = render_html_to_png(input_path, out_dir,
                                            width=args.width, height=args.height,
                                            dpr=args.dpr, full_page=args.fullpage,
                                            wait_for=args.wait_for, user_agent=args.user_agent,
                                            timeout=args.timeout)
    print("\nDone.")
    print("To serve the output folder on your local network (Windows):")
    print(f"  1) Open a PowerShell/CMD prompt in {out_dir.resolve()}")
    print("  2) Run: python -m http.server 8000")
    print("  3) Find your PC's local IP address with: ipconfig (look for IPv4 under Wi-Fi adapter)")
    print("  4) Open on another device on the same Wi-Fi: http://<your-ip>:8000")
    print("\nIf you want a public URL, use ngrok (https://ngrok.com):")
    print("  ngrok http 8000")
    print("\nIf Windows firewall blocks access, allow Python or open port 8000, e.g.:")
    print('  netsh advfirewall firewall add rule name="Python HTTP Server 8000" dir=in action=allow protocol=TCP localport=8000')
    print("\nEnjoy!")

if __name__ == "__main__":
    main()