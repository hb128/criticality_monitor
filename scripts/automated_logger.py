#!/usr/bin/env python3
"""
Automated Location Logger Script

This script continuously logs location data from the Critical Mass API.

Usage:
    python automated_logger.py [options]

Options:
    --interval SECONDS    Interval between logs in seconds (default: 60)
    --log-dir PATH       Custom logging directory (default: cm_logs/automated)
    --max-runs COUNT     Maximum number of logging runs (default: unlimited)
    --verbose            Enable verbose output
"""

import argparse
import sys
import time
import signal
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add the parent directory to sys.path to import cm_modular
sys.path.insert(0, str(Path(__file__).parent.parent))

from cm_modular.location_logger import log_locations


class AutomatedLogger:
    """Automated location logger with configurable intervals and options."""
    
    def __init__(self, 
                 interval: int = 60,
                 log_dir: str = "cm_logs/automated",
                 max_runs: Optional[int] = None,
                 verbose: bool = False):
        """
        Initialize the automated logger.
        
        Args:
            interval (int): Seconds between logging runs
            log_dir (str): Directory to save logs and maps
            center_location (tuple): Map center coordinates (lat, lon)
            zoom_start (int): Initial map zoom level
            max_runs (int, optional): Maximum number of runs (None = unlimited)
            verbose (bool): Enable verbose output
        """
        self.interval = interval
        self.log_dir = log_dir
        self.max_runs = max_runs
        self.verbose = verbose
        
        self.run_count = 0
        self.running = False
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.running = False
    
    def _log_message(self, message: str):
        """Log a message with timestamp if verbose mode is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{timestamp}] {message}")
    
    def run_single_log(self) -> bool:
        """
        Run a single logging operation.
        
        Returns:
            bool: True if successful, False if failed
        """
        try:
            self._log_message(f"Starting logging run #{self.run_count + 1}")
            
            positions = log_locations(self.log_dir)
            
            if len(positions) > 0:
                self._log_message(f"Successfully logged {len(positions)} positions")
                return True
            else:
                self._log_message("No positions logged (API might be unavailable)")
                return False
                
        except Exception as e:
            print(f"Error during logging run: {e}")
            return False
    
    def start(self):
        """Start the automated logging process."""
        print(f"Starting automated location logger...")
        print(f"Interval: {self.interval} seconds")
        print(f"Log directory: {self.log_dir}")
        print(f"Max runs: {self.max_runs if self.max_runs else 'unlimited'}")
        print(f"Press Ctrl+C to stop")
        print("-" * 50)
        
        # Create log directory
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.running = True
        
        while self.running:
            # Check if we've reached the maximum number of runs
            if self.max_runs and self.run_count >= self.max_runs:
                print(f"Reached maximum number of runs ({self.max_runs}). Stopping.")
                break
            
            # Run logging operation
            start_time = time.time()
            success = self.run_single_log()
            self.run_count += 1
            
            if success:
                print(f"Run #{self.run_count} completed successfully")
            else:
                print(f"Run #{self.run_count} failed")
            
            # Calculate sleep time (accounting for processing time)
            processing_time = time.time() - start_time
            sleep_time = max(0, self.interval - processing_time)
            
            if self.running and sleep_time > 0:
                self._log_message(f"Waiting {sleep_time:.1f} seconds until next run...")
                
                # Sleep in small intervals to allow for graceful shutdown
                slept = 0
                while slept < sleep_time and self.running:
                    chunk = min(1.0, sleep_time - slept)
                    time.sleep(chunk)
                    slept += chunk
        
        print(f"\nLogging stopped. Total runs completed: {self.run_count}")

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Automated location logger for Critical Mass data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python automated_logger.py                           # Default settings
  python automated_logger.py --interval 30            # Log every 30 seconds
  python automated_logger.py --log-dir my_logs        # Custom directory
  python automated_logger.py --max-runs 10 --verbose  # 10 runs with verbose output
        """
    )
    
    parser.add_argument(
        '--interval', 
        type=int, 
        default=15,
        help='Interval between logs in seconds (default: 60)'
    )
    
    parser.add_argument(
        '--log-dir', 
        type=str, 
        default='cm_logs/automated',
        help='Custom logging directory (default: cm_logs/automated)'
    )
    
    parser.add_argument(
        '--max-runs', 
        type=int, 
        default=None,
        help='Maximum number of logging runs (default: unlimited)'
    )
    
    parser.add_argument(
        '--use-sample', 
        action='store_true',
        help='Use sample data instead of API calls (for testing)'
    )
    
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.interval < 1:
        print("Error: Interval must be at least 1 second")
        sys.exit(1)
    
    if args.max_runs is not None and args.max_runs < 1:
        print("Error: Max runs must be at least 1")
        sys.exit(1)
    
    # Create and start the logger
    logger = AutomatedLogger(
        interval=args.interval,
        log_dir=args.log_dir,
        max_runs=args.max_runs,
        verbose=args.verbose
    )
    
    try:
        logger.start()
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()