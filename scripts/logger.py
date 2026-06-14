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
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import logging

from cm_modular import db

# Add the parent directory to sys.path to import cm_modular
sys.path.insert(0, str(Path(__file__).parent.parent))

from cm_modular.location_logger import load_locations

class AutomatedLogger:
    """Automated location logger with configurable intervals and options."""
    
    def __init__(self, 
                 interval: int,
                 db_path: str,
                 max_runs: Optional[int] = None,
                 loglevel = logging.INFO):
        """
        Initialize the automated logger.
        
        Args:
            interval (int): Seconds between logging runs
            db_path (str): Path to duchdb database
            max_runs (int, optional): Maximum number of runs (None = unlimited)
        """
        self.interval = interval
        self.db_path = db_path
        self.max_runs = max_runs
        
        self.run_count = 0
        self.running = False
        
        logging.basicConfig(format='[%(asctime)s] %(levelname)s:%(name)s:%(message)s', level=loglevel)
        self.log = logging.getLogger(self.__class__.__name__)


        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.log.info(f"Received signal {signum}. Shutting down gracefully...")
        self.running = False
    
    def run_single_log(self) -> bool:
        """
        Run a single logging operation.
        
        Returns:
            bool: True if successful, False if failed
        """
        try:
            self.log.info(f"Starting logging run #{self.run_count + 1}")
            positions = load_locations()
            position_count = len(positions.get('locations', []))

            ingested_at = datetime.now(timezone.utc)
            df = db.observations_from_api_payload(
                positions,
                ingested_at=ingested_at,
            )
            db.insert_observations(self.db_conn, df)
            if position_count > 0:
                self.log.info(f"Successfully logged {position_count} positions.")
                return True
            else:
                self.log.warning(f"No positions logged (API might be unavailable)")
                return False
                
        except Exception as e:
            self.log.error(f"Error during logging run: {e}")
            return False
    
    def start(self):
        """Start the automated logging process."""
        self.log.info(f"Starting automated location logger...")
        self.log.info(f"Interval: {self.interval} seconds")
        self.log.info(f"Log database: {self.db_path}")
        self.log.info(f"Max runs: {self.max_runs if self.max_runs else 'unlimited'}")
        self.log.info(f"Press Ctrl+C to stop")
        
        # Create database
        self.db_conn = db.connect(self.db_path)
        db.init_db(self.db_conn)
        self.running = True
        
        while self.running:
            # Check if we've reached the maximum number of runs
            if self.max_runs and self.run_count >= self.max_runs:
                self.log.info(f"Reached maximum number of runs ({self.max_runs}). Stopping.")
                break
            
            # Run logging operation
            start_time = time.time()
            success = self.run_single_log()
            self.run_count += 1
            
            if success:
                self.log.info(f"Run #{self.run_count} completed successfully")
            else:
                self.log.error(f"Run #{self.run_count} failed")
            
            # Calculate sleep time (accounting for processing time)
            processing_time = time.time() - start_time
            sleep_time = max(0, self.interval - processing_time)
            
            if self.running and sleep_time > 0:
                self.log.info(f"Waiting {sleep_time:.1f} seconds until next run...")
                
                # Sleep in small intervals to allow for graceful shutdown
                slept = 0
                while slept < sleep_time and self.running:
                    chunk = min(1.0, sleep_time - slept)
                    time.sleep(chunk)
                    slept += chunk
        
        self.log.info(f"Logging stopped. Total runs completed: {self.run_count}")

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Automated location logger for Criticality Monitor data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python automated_logger.py                           # Default settings
  python automated_logger.py --interval 30            # Log every 30 seconds
  python automated_logger.py --path-db my-db        # Custom directory
  python automated_logger.py --max-runs 10            # 10 runs 
        """
    )
    
    parser.add_argument('--interval', type=int, default=15, help='Interval between logs in seconds (default: %(default)s)')
    parser.add_argument('--db-path', type=str, default='data.db', help='Custom db path (default: %(default)s)')
    parser.add_argument('--max-runs', type=int, default=None, help='Maximum number of logging runs (default: %(default)s)')
    parser.add_argument(
        '-d', '--debug',
        help="Print lots of debugging statements",
        action="store_const", dest="loglevel", const=logging.DEBUG,
        default=logging.INFO,
    )
    # parser.add_argument(
    #     '-v', '--verbose',
    #     help="Be verbose",
    #     action="store_const", dest="loglevel", const=logging.INFO,
    # )
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
        db_path=args.db_path,
        max_runs=args.max_runs,
        loglevel = args.loglevel
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