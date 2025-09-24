#!/usr/bin/env python3
"""
Service Monitor Script

Monitors the health and status of all Criticality Monitor services.
Provides logging, alerting, and basic health checks.
"""

import argparse
import time
import sys
import os
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class ServiceMonitor:
    """Monitors Criticality Monitor services and logs their status."""
    
    def __init__(self, 
                 interval: int = 60,
                 log_dir: Path = None):
        """
        Initialize the service monitor.
        
        Args:
            interval: Check interval in seconds
            log_dir: Directory to write monitoring logs
        """
        self.interval = interval
        self.log_dir = log_dir or Path("/app/logs")
        
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Service status tracking
        self.service_status: Dict[str, Dict] = {}
        
        print(f"Service monitor initialized")
        print(f"Check interval: {self.interval}s")
        print(f"Log directory: {self.log_dir}")
    
    def check_docker_services(self) -> Dict[str, Dict]:
        """Check status of Docker services."""
        services = {}
        
        try:
            # Get container status using docker ps
            result = subprocess.run(
                ["docker", "ps", "--format", "json"],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line:
                    container_info = json.loads(line)
                    name = container_info.get('Names', 'unknown')
                    
                    # Only monitor our services
                    if name.startswith('cm-'):
                        services[name] = {
                            'status': container_info.get('State', 'unknown'),
                            'uptime': container_info.get('Status', 'unknown'),
                            'image': container_info.get('Image', 'unknown'),
                            'ports': container_info.get('Ports', ''),
                            'last_check': datetime.now().isoformat()
                        }
            
        except subprocess.CalledProcessError as e:
            print(f"Error checking Docker services: {e}")
        except json.JSONDecodeError as e:
            print(f"Error parsing Docker output: {e}")
        except FileNotFoundError:
            print("Docker command not found - running without Docker monitoring")
        
        return services
    
    def check_file_health(self) -> Dict[str, Dict]:
        """Check health based on file system indicators."""
        health = {}
        
        # Check if log files are being updated
        log_dirs = [
            "/app/cm_logs/automated",
            "/app/cm_logs/hamburg",
            "/app/cm_logs/berlin"
        ]
        
        for log_dir in log_dirs:
            log_path = Path(log_dir)
            city = log_path.name
            
            if log_path.exists():
                # Find most recent file
                files = list(log_path.glob('*.txt'))
                if files:
                    latest_file = max(files, key=lambda f: f.stat().st_mtime)
                    age_seconds = time.time() - latest_file.stat().st_mtime
                    
                    health[f"logs_{city}"] = {
                        'latest_file': str(latest_file),
                        'age_seconds': age_seconds,
                        'status': 'healthy' if age_seconds < 300 else 'stale',
                        'last_check': datetime.now().isoformat()
                    }
                else:
                    health[f"logs_{city}"] = {
                        'status': 'no_files',
                        'last_check': datetime.now().isoformat()
                    }
            else:
                health[f"logs_{city}"] = {
                    'status': 'missing_directory',
                    'last_check': datetime.now().isoformat()
                }
        
        # Check if CSV files are being updated
        csv_files = [
            "/app/site/hamburg/distances.csv",
            "/app/site/berlin/distances.csv"
        ]
        
        for csv_file in csv_files:
            csv_path = Path(csv_file)
            city = csv_path.parent.name
            
            if csv_path.exists():
                age_seconds = time.time() - csv_path.stat().st_mtime
                health[f"csv_{city}"] = {
                    'file': str(csv_path),
                    'age_seconds': age_seconds,
                    'status': 'healthy' if age_seconds < 3600 else 'stale',  # 1 hour threshold
                    'last_check': datetime.now().isoformat()
                }
            else:
                health[f"csv_{city}"] = {
                    'status': 'missing_file',
                    'last_check': datetime.now().isoformat()
                }
        
        return health
    
    def write_status_log(self, status: Dict):
        """Write status information to log file."""
        timestamp = datetime.now()
        log_file = self.log_dir / f"monitor_{timestamp.strftime('%Y%m%d')}.log"
        
        log_entry = {
            'timestamp': timestamp.isoformat(),
            'status': status
        }
        
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error writing log: {e}")
    
    def print_status_summary(self, docker_status: Dict, file_health: Dict):
        """Print a summary of current status."""
        print(f"\n=== Status Report [{datetime.now()}] ===")
        
        # Docker services
        print("\nDocker Services:")
        if docker_status:
            for service, info in docker_status.items():
                status = info.get('status', 'unknown')
                uptime = info.get('uptime', 'unknown')
                print(f"  {service}: {status} ({uptime})")
        else:
            print("  No Docker services detected")
        
        # File health
        print("\nFile Health:")
        for check, info in file_health.items():
            status = info.get('status', 'unknown')
            if 'age_seconds' in info:
                age_min = info['age_seconds'] / 60
                print(f"  {check}: {status} (last updated {age_min:.1f} min ago)")
            else:
                print(f"  {check}: {status}")
        
        print("=" * 50)
    
    def run(self):
        """Main monitoring loop."""
        print("Starting service monitor...")
        
        while True:
            try:
                # Check Docker services
                docker_status = self.check_docker_services()
                
                # Check file-based health indicators
                file_health = self.check_file_health()
                
                # Combine status
                full_status = {
                    'docker_services': docker_status,
                    'file_health': file_health
                }
                
                # Log status
                self.write_status_log(full_status)
                
                # Print summary
                self.print_status_summary(docker_status, file_health)
                
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                print("\nStopping service monitor...")
                break
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(self.interval)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Monitor Criticality Monitor services")
    
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60)"
    )
    
    parser.add_argument(
        "--log-dir",
        type=str,
        default="/app/logs",
        help="Directory for monitoring logs (default: /app/logs)"
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    monitor = ServiceMonitor(
        interval=args.interval,
        log_dir=Path(args.log_dir)
    )
    
    try:
        monitor.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()