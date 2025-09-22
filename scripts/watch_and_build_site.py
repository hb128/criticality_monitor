#!/usr/bin/env python3
"""
Watch and Build Site Script

Monitors CSV files from batch processors and builds enhanced websites.
Includes city-specific sites and a leaderboard across all cities.
"""

import argparse
import time
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add the parent directory to sys.path to import cm_modular
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.build_enhanced_site import build_enhanced_site


class SiteBuilder:
    """Watches for updated CSV files and builds enhanced websites."""
    
    def __init__(self, 
                 interval: int = 300,
                 primary_city: str = "hamburg",
                 site_root: Path = None):
        """
        Initialize the site builder.
        
        Args:
            interval: Check interval in seconds
            primary_city: Primary city for main site
            site_root: Root directory for all sites
        """
        self.interval = interval
        self.primary_city = primary_city
        self.site_root = site_root or Path("/app/site")
        
        # Track last modification times
        self.last_modified: Dict[str, float] = {}
        
        print(f"Site builder initialized")
        print(f"Check interval: {self.interval}s")
        print(f"Primary city: {self.primary_city}")
        print(f"Site root: {self.site_root}")
    
    def find_csv_files(self) -> Dict[str, Path]:
        """Find all distances.csv files in city subdirectories."""
        csv_files = {}
        
        for city_dir in self.site_root.iterdir():
            if city_dir.is_dir():
                csv_path = city_dir / "distances.csv"
                if csv_path.exists():
                    csv_files[city_dir.name] = csv_path
                    
        return csv_files
    
    def check_for_updates(self, csv_files: Dict[str, Path]) -> List[str]:
        """Check which CSV files have been updated."""
        updated_cities = []
        
        for city, csv_path in csv_files.items():
            try:
                current_mtime = csv_path.stat().st_mtime
                last_mtime = self.last_modified.get(city, 0)
                
                if current_mtime > last_mtime:
                    updated_cities.append(city)
                    self.last_modified[city] = current_mtime
                    
            except OSError:
                # File might have been deleted or moved
                continue
                
        return updated_cities
    
    def build_city_site(self, city: str, csv_path: Path):
        """Build enhanced site for a specific city."""
        try:
            output_dir = self.site_root / city
            
            print(f"Building site for {city}...")
            
            build_enhanced_site(
                csv_path=csv_path,
                outdir=output_dir,
                city=city.title(),
                copy_maps=True,
                maps_subdir="maps",
                recent_limit=30,
                leaderboard_limit=10
            )
            
            print(f"Site built successfully for {city}")
            
        except Exception as e:
            print(f"Error building site for {city}: {e}")
    
    def build_combined_leaderboard(self, csv_files: Dict[str, Path]):
        """Build a combined leaderboard across all cities."""
        try:
            import pandas as pd
            
            # Combine data from all cities
            all_data = []
            
            for city, csv_path in csv_files.items():
                try:
                    df = pd.read_csv(csv_path)
                    df['city'] = city.title()
                    all_data.append(df)
                except Exception as e:
                    print(f"Error reading {csv_path}: {e}")
                    continue
            
            if not all_data:
                print("No data available for combined leaderboard")
                return
            
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # Write combined CSV
            combined_csv = self.site_root / "combined_distances.csv"
            combined_df.to_csv(combined_csv, index=False)
            
            # Build main site with combined data
            main_output = self.site_root / "main"
            
            build_enhanced_site(
                csv_path=combined_csv,
                outdir=main_output,
                city="Critical Mass Global",
                copy_maps=False,  # Don't copy individual maps
                recent_limit=50,
                leaderboard_limit=20
            )
            
            print("Combined leaderboard site built successfully")
            
        except Exception as e:
            print(f"Error building combined leaderboard: {e}")
    
    def run(self):
        """Main site building loop."""
        print("Starting site builder...")
        
        while True:
            try:
                csv_files = self.find_csv_files()
                
                if not csv_files:
                    print(f"[{datetime.now()}] No CSV files found")
                    time.sleep(self.interval)
                    continue
                
                updated_cities = self.check_for_updates(csv_files)
                
                if updated_cities:
                    print(f"[{datetime.now()}] Updates detected for: {', '.join(updated_cities)}")
                    
                    # Build individual city sites
                    for city in updated_cities:
                        self.build_city_site(city, csv_files[city])
                    
                    # Build combined leaderboard
                    self.build_combined_leaderboard(csv_files)
                    
                    print("All sites updated successfully")
                else:
                    print(f"[{datetime.now()}] No updates detected")
                
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                print("\nStopping site builder...")
                break
            except Exception as e:
                print(f"Error in site builder loop: {e}")
                time.sleep(self.interval)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Watch CSV files and build enhanced websites")
    
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300)"
    )
    
    parser.add_argument(
        "--primary-city",
        type=str,
        default="hamburg",
        help="Primary city name (default: hamburg)"
    )
    
    parser.add_argument(
        "--site-root",
        type=str,
        default="/app/site",
        help="Root directory for sites (default: /app/site)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    builder = SiteBuilder(
        interval=args.interval,
        primary_city=args.primary_city,
        site_root=Path(args.site_root)
    )
    
    try:
        builder.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()