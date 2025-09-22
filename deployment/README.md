# Critical Mass Server Deployment

This directory contains everything needed to deploy and manage multiple Critical Mass services on a server.

## Overview

The deployment architecture consists of:

1. **automated-logger** - Continuously logs location data from the Critical Mass API
2. **batch-processor-hamburg** - Processes Hamburg log files through the pipeline
3. **batch-processor-berlin** - Processes Berlin log files through the pipeline  
4. **site-builder** - Builds enhanced websites from processed data
5. **web-server** - Nginx server to serve the generated sites
6. **monitoring** - Monitors all services and logs their health

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Git (optional, for updates)

### Starting Services

**Linux/macOS:**
```bash
cd deployment
chmod +x manage.sh
./manage.sh start
```

**Windows:**
```cmd
cd deployment
manage.bat start
```

### Accessing the Sites

- Main leaderboard: http://localhost:8080/
- Hamburg site: http://localhost:8080/hamburg/
- Berlin site: http://localhost:8080/berlin/
- Health check: http://localhost:8080/health

## Management Commands

### Linux/macOS (`manage.sh`)

```bash
./manage.sh start                    # Start all services
./manage.sh stop                     # Stop all services
./manage.sh restart                  # Restart all services
./manage.sh status                   # Show service status
./manage.sh logs [service]           # Show logs (all or specific service)
./manage.sh update                   # Update and rebuild services
./manage.sh scale <service> <n>      # Scale a service to n replicas
./manage.sh disk                     # Show disk usage
./manage.sh backup [directory]       # Backup data
./manage.sh cleanup [days]           # Clean up old files (default: 7 days)
```

### Windows (`manage.bat`)

```cmd
manage.bat start                     # Start all services
manage.bat stop                      # Stop all services
manage.bat restart                   # Restart all services
manage.bat status                    # Show service status
manage.bat logs [service]            # Show logs
manage.bat update                    # Update and rebuild services
manage.bat disk                      # Show disk usage
manage.bat backup [directory]        # Backup data
```

## Configuration

### Environment Variables

You can customize the deployment by setting environment variables in a `.env` file:

```env
# Logging configuration
INTERVAL=60                          # Automated logger interval (seconds)
LOG_DIR=cm_logs/automated           # Log directory

# Processing configuration
WORKERS=2                           # Number of worker processes per city

# Site builder configuration
WATCH_INTERVAL=300                  # Site rebuild interval (seconds)
PRIMARY_CITY=hamburg               # Primary city for main site

# Monitoring configuration
CHECK_INTERVAL=60                  # Monitoring check interval (seconds)
```

### Adding New Cities

To add a new city (e.g., Munich):

1. Add a new service in `docker-compose.yml`:
```yaml
batch-processor-munich:
  build: .
  container_name: cm-batch-munich
  restart: unless-stopped
  volumes:
    - ./cm_logs:/app/cm_logs
    - ./site:/app/site
    - ./config:/app/config
  environment:
    - WATCH_DIR=/app/cm_logs/munich
    - OUTPUT_DIR=/app/site/munich
    - CITY=munich
    - WORKERS=2
  command: python scripts/watch_and_process.py --city munich --watch-dir /app/cm_logs/munich --output-dir /app/site/munich --workers 2
```

2. Create the log directory: `mkdir cm_logs/munich`

3. Update nginx configuration to serve the new city site

## Architecture Details

### Service Dependencies

```
automated-logger (logs data)
    ↓
batch-processor-* (processes logs → CSV + maps)
    ↓  
site-builder (CSV → enhanced websites)
    ↓
web-server (serves websites)

monitoring (watches all services)
```

### Data Flow

1. **Location Logging**: `automated_logger.py` fetches location data from the Critical Mass API every 60 seconds and saves to `cm_logs/automated/`

2. **File Processing**: Each `watch_and_process.py` instance monitors its city's log directory and processes new files through the pipeline, generating:
   - Individual map HTML files
   - `distances.csv` with metrics

3. **Site Building**: `watch_and_build_site.py` monitors CSV files and builds enhanced websites with:
   - Recent rides plot
   - Leaderboards  
   - Interactive maps
   - City-specific and combined sites

4. **Web Serving**: Nginx serves all generated sites with proper routing

5. **Monitoring**: `monitor_services.py` tracks service health and logs status

### Directory Structure

```
deployment/
├── docker-compose.yml              # Main service configuration
├── Dockerfile                      # Application container
├── manage.sh                       # Linux/macOS management script
├── manage.bat                      # Windows management script
├── nginx.conf                      # Web server configuration
├── healthcheck.py                  # Container health checks
└── README.md                       # This documentation

../scripts/                         # Application scripts (shared)
├── automated_logger.py             # Original automated logger
├── batch_build.py                  # Original batch processor
├── build_enhanced_site.py          # Original site builder
├── watch_and_process.py            # File watcher and processor
├── watch_and_build_site.py         # Site builder watcher
└── monitor_services.py             # Service monitoring

../cm_logs/                         # Log data (mounted volume)
├── automated/                      # Auto-logged data
├── hamburg/                        # Hamburg-specific logs
└── berlin/                         # Berlin-specific logs

../site/                            # Generated websites (mounted volume)
├── main/                          # Combined leaderboard site
├── hamburg/                       # Hamburg-specific site
└── berlin/                        # Berlin-specific site
```

## Monitoring and Logs

### Service Health

Check service status:
```bash
./manage.sh status
```

View service logs:
```bash
./manage.sh logs                    # All services
./manage.sh logs automated-logger   # Specific service
```

### Monitoring Dashboard

The monitoring service logs to `/app/logs/monitor_YYYYMMDD.log` with JSON entries containing:
- Docker service status
- File update timestamps  
- Health check results

### Log Rotation

Docker handles log rotation automatically with the configured limits:
- Max log file size: 100MB
- Max log files: 3 per service

## Scaling and Performance

### Horizontal Scaling

Scale individual services:
```bash
./manage.sh scale batch-processor-hamburg 4   # Run 4 Hamburg processors
```

### Resource Management

Each service has resource limits defined in docker-compose.yml. Adjust based on your server capacity:

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 1G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### Performance Tuning

- **CPU**: Increase `workers` for batch processing
- **Memory**: Adjust Docker memory limits
- **I/O**: Use SSD storage for log directories
- **Network**: Ensure stable internet for API calls

## Backup and Recovery

### Automated Backups

Create a backup:
```bash
./manage.sh backup /backup/critical_mass
```

This backs up:
- All log files (`cm_logs/`)
- Generated sites (`site/`)
- Configuration files (`config/`)

### Recovery

To restore from backup:
1. Stop services: `./manage.sh stop`
2. Restore directories from backup
3. Start services: `./manage.sh start`

## Troubleshooting

### Common Issues

**Services won't start:**
- Check Docker is running: `docker --version`
- Check ports aren't in use: `netstat -tlnp | grep 8080`
- Check logs: `./manage.sh logs`

**No data being processed:**
- Check API connectivity from automated-logger logs
- Verify log directories exist and are writable
- Check file permissions

**Websites not updating:**
- Check CSV files are being generated
- Verify site-builder service is running
- Check nginx configuration

**High resource usage:**
- Reduce worker counts in environment variables
- Implement log cleanup: `./manage.sh cleanup 3`
- Scale down services: `./manage.sh scale batch-processor-hamburg 1`

### Log Analysis

View recent errors across all services:
```bash
docker logs cm-automated-logger 2>&1 | grep -i error | tail -20
```

Check specific service health:
```bash
docker exec cm-monitoring python healthcheck.py
```

## Security Considerations

- Services run as non-root user in containers
- No external ports exposed except web server (8080)
- Nginx includes security headers
- Container isolation prevents service interference
- Log files contain no sensitive data (only GPS coordinates)

## Production Deployment

For production deployment:

1. **Use environment-specific configuration:**
   - Production `.env` file
   - SSL certificates for nginx
   - Domain names instead of localhost

2. **Set up external monitoring:**
   - Prometheus/Grafana for metrics
   - Log aggregation (ELK stack)
   - Alerting for service failures

3. **Implement backup automation:**
   - Scheduled backup scripts
   - Off-site backup storage
   - Backup verification

4. **Configure reverse proxy:**
   - SSL termination
   - Load balancing
   - Rate limiting