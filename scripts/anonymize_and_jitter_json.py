import json
import math
import random
from pathlib import Path


R_EARTH = 6_371_000.0  # metres


def jitter_locations(json_in: str, json_out: str, max_offset_m: float = 5.0) -> None:
    json_in_path = Path(json_in)
    json_out_path = Path(json_out)

    with json_in_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    locations = data.get("locations", {})
    if not locations:
        raise ValueError("No 'locations' key or empty locations in JSON")

    # Collect lat/lon degrees for reference point (same idea as GeoUtils.deg2meters)
    lats_deg = []
    lons_deg = []
    for entry in locations.values():
        lats_deg.append(entry["latitude"] / 1_000_000.0)
        lons_deg.append(entry["longitude"] / 1_000_000.0)

    # Median reference point
    def median(xs):
        xs = sorted(xs)
        n = len(xs)
        m = n // 2
        if n % 2 == 1:
            return xs[m]
        return 0.5 * (xs[m - 1] + xs[m])

    lat0_deg = median(lats_deg)
    lon0_deg = median(lons_deg)

    lat0_rad = math.radians(lat0_deg)
    lon0_rad = math.radians(lon0_deg)

    new_locations = {}
    for i, (_, entry) in enumerate(locations.items(), start=1):
        lat_deg = entry["latitude"] / 1_000_000.0
        lon_deg = entry["longitude"] / 1_000_000.0

        # Forward: degrees -> local metres (equirectangular)
        lat_rad = math.radians(lat_deg)
        lon_rad = math.radians(lon_deg)

        x = (lon_rad - lon0_rad) * math.cos(lat0_rad) * R_EARTH
        y = (lat_rad - lat0_rad) * R_EARTH

        # Random jitter in metres
        dx = random.uniform(-max_offset_m, max_offset_m)
        dy = random.uniform(-max_offset_m, max_offset_m)

        x_j = x + dx
        y_j = y + dy

        # Back: local metres -> degrees
        lon_rad_j = x_j / (R_EARTH * math.cos(lat0_rad)) + lon0_rad
        lat_rad_j = y_j / R_EARTH + lat0_rad

        lat_j_deg = math.degrees(lat_rad_j)
        lon_j_deg = math.degrees(lon_rad_j)

        new_entry = dict(entry)
        new_entry["latitude"] = int(round(lat_j_deg * 1_000_000))
        new_entry["longitude"] = int(round(lon_j_deg * 1_000_000))

        new_id = f"id_{i}"
        new_locations[new_id] = new_entry

        # Debug: approximate offsets in metres actually applied
        approx_dlat_m = (lat_j_deg - lat_deg) * math.pi / 180.0 * R_EARTH
        approx_dlon_m = (lon_j_deg - lon_deg) * math.pi / 180.0 * R_EARTH * math.cos(lat0_rad)
        print(
            f"{new_id}: dlat ≈ {approx_dlat_m:.2f} m, "
            f"dlon ≈ {approx_dlon_m:.2f} m"
        )

    data["locations"] = new_locations

    with json_out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote anonymised, jittered JSON to {json_out_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("json_in", help="Input Critical Maps JSON")
    parser.add_argument(
        "--out",
        help="Output JSON path (default: add '_jittered' before suffix)",
    )
    parser.add_argument(
        "--max-offset-m",
        type=float,
        default=50.0,
        help="Max absolute jitter in metres for x and y (default: 50)",
    )

    args = parser.parse_args()
    out_path = args.out
    if out_path is None:
        p = Path(args.json_in)
        out_path = str(p.with_name(p.stem + "_jittered" + p.suffix))

    jitter_locations(args.json_in, out_path, max_offset_m=args.max_offset_m)