#!/usr/bin/env python3
"""
Automated Location Logger Script

This script continuously logs location data from the Criticality Maps API.
"""

import argparse
import sys
import time
import signal
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import shutil

# Add the parent directory to sys.path to import cm_modular
sys.path.insert(0, str(Path(__file__).parent.parent))

from cm_modular.location_logger import log_locations


class AutomatedLogger:
    """Automated location logger with configurable intervals and options."""
    
    def __init__(self, 
                 interval: int,
                 log_dir: str,
                 max_runs: Optional[int] = None,
                 verbose: bool = False,
                 debug_source: Optional[str] = None):
        """
        Initialize the automated logger.
        
        Args:
            interval (int): Seconds between logging runs
            log_dir (str): Directory to save logs and maps
            max_runs (int, optional): Maximum number of runs (None = unlimited)
            verbose (bool): Enable verbose output
            debug_source (str, optional): Directory containing txt files for debug mode
        """
        self.interval = interval
        self.log_dir = log_dir
        self.max_runs = max_runs
        self.verbose = verbose
        self.debug_source = debug_source
        
        self.run_count = 0
        self.running = False
        
        # Debug mode state tracking
        self.debug_files = []
        self.debug_file_index = 0
        
        if self.debug_source:
            self._load_debug_files()
        
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
    
    def _load_debug_files(self):
        """Load and sort txt files from debug source directory."""
        if not self.debug_source:
            return
            
        debug_path = Path(self.debug_source)
        if not debug_path.exists():
            raise FileNotFoundError(f"Warning: Debug source directory does not exist: {debug_path}")
            
        # Find all .txt files and sort them alphabetically
        self.debug_files = sorted(debug_path.glob("*.txt"))
        
        if not self.debug_files:
            raise FileNotFoundError(f"Warning: No .txt files found in debug source directory: {debug_path}")
        else:
            self._log_message(f"Loaded {len(self.debug_files)} debug files from {debug_path}")
    
    def _copy_debug_file(self) -> int:
        """
        Copy the next debug file to the log directory.
        
        Returns:
            int: Number of lines copied (simulating positions count)
        """
        if not self.debug_files:
            return 0
            
        if self.debug_file_index >= len(self.debug_files):
            self._log_message("All debug files processed, cycling back to start")
            self.debug_file_index = 0
            
        source_file = self.debug_files[self.debug_file_index]
        self.debug_file_index += 1
        
        # Generate timestamp-based filename for the copy
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest_filename = f"{timestamp}.txt"
        dest_path = Path(self.log_dir) / dest_filename
        
        # Copy the file content
        shutil.copy2(source_file, dest_path)
        
        # Count lines to simulate position count
        with open(source_file, 'r', encoding='utf-8') as f:
            line_count = sum(1 for line in f if line.strip())
        
        self._log_message(f"Copied debug file: {source_file.name} -> {dest_filename} ({line_count} lines)")
        return line_count

    
    def run_single_log(self) -> bool:
        """
        Run a single logging operation.
        
        Returns:
            bool: True if successful, False if failed
        """
        try:
            self._log_message(f"Starting logging run #{self.run_count + 1}")
            
            if self.debug_source:
                # Debug mode: copy a file from debug source
                position_count = self._copy_debug_file()
            else:
                # Normal mode: use API
                positions = log_locations(self.log_dir)
                position_count = len(positions)
            
            if position_count > 0:
                mode = "debug file" if self.debug_source else "API"
                self._log_message(f"Successfully logged {position_count} positions from {mode}")
                return True
            else:
                mode = "debug directory" if self.debug_source else "API"
                self._log_message(f"No positions logged ({mode} might be unavailable)")
                return False
                
        except Exception as e:
            print(f"Error during logging run: {e}")
            return False
    
    def start(self):
        """Start the automated logging process."""
        print(f"Starting automated location logger...")
        print(f"Mode: {'Debug (file replay)' if self.debug_source else 'Normal (API)'}")
        if self.debug_source:
            print(f"Debug source: {self.debug_source} ({len(self.debug_files)} files)")
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
        description="Automated location logger for Criticality Monitor data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python automated_logger.py                           # Default settings
  python automated_logger.py --interval 30            # Log every 30 seconds
  python automated_logger.py --log-dir my_logs        # Custom directory
  python automated_logger.py --max-runs 10 --verbose  # 10 runs with verbose output
  python automated_logger.py --debug-source logs/20220624  # Debug mode with historical data
        """
    )
    
    parser.add_argument('--interval', type=int, default=15, help='Interval between logs in seconds (default: %(default)s)')
    parser.add_argument('--log-dir', type=str, default='data/logs', help='Custom logging directory (default: %(default)s)')
    parser.add_argument('--max-runs', type=int, default=None, help='Maximum number of logging runs (default: %(default)s)')
    parser.add_argument('--use-sample', action='store_true', help='Use sample data instead of API calls (for testing)')
    parser.add_argument('--debug-source', type=str, default=None, help='Directory containing txt files for debug mode (replays files instead of using API)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
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
        verbose=args.verbose,
        debug_source=args.debug_source
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