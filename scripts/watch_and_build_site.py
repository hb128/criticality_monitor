#!/usr/bin/env python3
"""
Watch and Build Site Script

Monitors JSON state files from batch processors and builds enhanced websites.
Includes city-specific sites and a leaderboard across all cities.
"""

import argparse
import time
import sys
import os
import json
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
    
    def find_state_files(self) -> Dict[str, Path]:
        """Find all batch state JSON files in city subdirectories."""
        state_files = {}
        
        for city_dir in self.site_root.iterdir():
            if city_dir.is_dir():
                state_path = city_dir / "results.json"
                if state_path.exists():
                    state_files[city_dir.name] = state_path
                    
        return state_files
    
    def check_for_updates(self, state_files: Dict[str, Path]) -> List[str]:
        """Check which state files have been updated."""
        updated_cities = []
        
        for city, state_path in state_files.items():
            try:
                current_mtime = state_path.stat().st_mtime
                last_mtime = self.last_modified.get(city, 0)
                
                if current_mtime > last_mtime:
                    updated_cities.append(city)
                    self.last_modified[city] = current_mtime
                    
            except OSError:
                # File might have been deleted or moved
                continue
                
        return updated_cities
    
    def load_results_from_state(self, state_path: Path) -> list[dict]:
        """Load results from a batch state JSON file."""
        try:
            with open(state_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('results', [])
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading state file {state_path}: {e}")
            return []
    
    def build_city_site(self, city: str, state_path: Path):
        """Build enhanced site for a specific city."""
        try:
            output_dir = self.site_root / city
            
            print(f"Building site for {city}...")
            
            # Use the JSON state file directly
            build_enhanced_site(
                data_path=state_path,
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
    
    def build_combined_leaderboard(self, state_files: Dict[str, Path]):
        """Build a combined leaderboard across all cities."""
        try:
            # Combine data from all cities
            all_results = []
            
            for city, state_path in state_files.items():
                try:
                    results = self.load_results_from_state(state_path)
                    for result in results:
                        result['city'] = city.title()
                        all_results.append(result)
                except Exception as e:
                    print(f"Error reading {state_path}: {e}")
                    continue
            
            if not all_results:
                print("No data available for combined leaderboard")
                return
            
            # Create a temporary JSON state file for the combined data
            combined_state = {
                'metadata': {
                    'last_run': datetime.now().isoformat(),
                    'total_files': len(state_files),
                    'total_results': len(all_results),
                    'version': '1.0',
                    'type': 'combined'
                },
                'processed_files': [],  # Not applicable for combined data
                'results': all_results
            }
            
            combined_state_path = self.site_root / ".combined_state.json"
            with open(combined_state_path, 'w', encoding='utf-8') as f:
                json.dump(combined_state, f, indent=2)
            
            # Build main site with combined data
            main_output = self.site_root / "main"
            
            build_enhanced_site(
                data_path=combined_state_path,
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
                state_files = self.find_state_files()
                
                if not state_files:
                    print(f"[{datetime.now()}] No state files found")
                    time.sleep(self.interval)
                    continue
                
                updated_cities = self.check_for_updates(state_files)
                
                if updated_cities:
                    print(f"[{datetime.now()}] Updates detected for: {', '.join(updated_cities)}")
                    
                    # Build individual city sites
                    for city in updated_cities:
                        self.build_city_site(city, state_files[city])
                    
                    # Build combined leaderboard
                    self.build_combined_leaderboard(state_files)
                    
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
    parser = argparse.ArgumentParser(description="Watch JSON state files and build enhanced websites")
    
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