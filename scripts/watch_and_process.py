#!/usr/bin/env python3
"""
Watch and Process Script

Monitors a directory for new files and processes them through the batch_build pipeline.
This script acts as a file watcher that automatically processes new log files.
"""

import argparse
import time
import os
import sys
from pathlib import Path
from typing import Set
from datetime import datetime

# Add the parent directory to sys.path to import cm_modular
sys.path.insert(0, str(Path(__file__).parent.parent))

from cm_modular.pipeline import PipelineConfig
from scripts.batch_build import run_batch


class FileWatcher:
    """Watches a directory and processes new files."""
    
    def __init__(self, 
                 watch_dir: Path,
                 output_dir: Path,
                 city: str = None,
                 workers: int = 1,
                 interval: int = 60,
                 patterns: list = None):
        """
        Initialize the file watcher.
        
        Args:
            watch_dir: Directory to watch for new files
            output_dir: Directory to output processed files
            city: City preset for pipeline configuration
            workers: Number of parallel workers
            interval: Check interval in seconds
            patterns: File patterns to watch for
        """
        self.watch_dir = Path(watch_dir)
        self.output_dir = Path(output_dir + "/" + city)
        self.city = city
        self.workers = workers
        self.interval = interval
        self.patterns = patterns or ['*.txt', '*.json']
        
        # Create directories
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"Watching directory: {self.watch_dir}")
        print(f"Output directory: {self.output_dir}")
        print(f"City: {self.city}")
        print(f"Workers: {self.workers}")
        print(f"Check interval: {self.interval}s")
        print(f"File patterns: {self.patterns}")
        print(f"Note: Using batch_build incremental processing")
    
    def process_new_files(self):
        """Process files through the batch pipeline (now handles incremental internally)."""
        print(f"\n[{datetime.now()}] Running batch processing...")
        
        # Create pipeline configuration
        cfg = PipelineConfig(city=self.city) if self.city else PipelineConfig()
        
        try:
            # Process files using batch_build with incremental processing
            state_path = run_batch(
                indir=self.watch_dir,
                outdir=self.output_dir,
                patterns=self.patterns,
                cfg=cfg,
                workers=self.workers,
                incremental=True  # Enable incremental processing for watchers
            )
            print(f"Batch processing completed. State saved to: {state_path}")
            
        except Exception as e:
            print(f"Error during batch processing: {e}")
    
    def run(self):
        """Main watch loop."""
        print("Starting file watcher...")
        
        while True:
            try:
                # Run batch processing (it will handle incremental processing internally)
                self.process_new_files()
                
                print(f"[{datetime.now()}] Waiting {self.interval} seconds until next check...")
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                print("\nStopping file watcher...")
                break
            except Exception as e:
                print(f"Error in watch loop: {e}")
                time.sleep(self.interval)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Watch directory and process new files")
    
    parser.add_argument(
        "--watch-dir",
        type=str,
        required=True,
        help="Directory to watch for new files"
    )
    
    parser.add_argument(
        "--output-dir", 
        type=str,
        required=True,
        help="Directory to output processed files"
    )
    
    parser.add_argument(
        "--city",
        type=str,
        default="hamburg",
        help="City preset for pipeline configuration"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1)"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--pattern",
        action="append",
        default=None,
        help="File patterns to watch (can repeat, default: *.txt, *.json)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    patterns = args.pattern if args.pattern else ['*.txt', '*.json']
    
    watcher = FileWatcher(
        watch_dir=args.watch_dir,
        output_dir=args.output_dir,
        city=args.city,
        workers=args.workers,
        interval=args.interval,
        patterns=patterns
    )
    
    try:
        watcher.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()