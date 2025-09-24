#!/bin/bash
set -e

# Criticality Monitor Server Management Script
# Usage: ./manage.sh [start|stop|restart|status|logs|update]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if Docker and Docker Compose are available
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        if ! docker compose version &> /dev/null; then
            error "Docker Compose is not installed or not in PATH"
            exit 1
        fi
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
}

# Start all services
start_services() {
    log "Starting Criticality Monitor services..."
    
    cd "$SCRIPT_DIR"
    
    # Create necessary directories
    mkdir -p ../cm_logs/{automated,hamburg,berlin}
    mkdir -p ../site/{hamburg,berlin,main}
    mkdir -p ../config
    mkdir -p ../logs
    
    # Build and start services
    $COMPOSE_CMD build
    $COMPOSE_CMD up -d
    
    success "Services started successfully"
    
    # Show status
    show_status
    
    # Show access information
    echo ""
    log "Access information:"
    echo "  Web interface: http://localhost:8080"
    echo "  Main leaderboard: http://localhost:8080/"
    echo "  Hamburg site: http://localhost:8080/hamburg/"
    echo "  Berlin site: http://localhost:8080/berlin/"
    echo "  Health check: http://localhost:8080/health"
}

# Stop all services
stop_services() {
    log "Stopping Criticality Monitor services..."
    
    cd "$SCRIPT_DIR"
    $COMPOSE_CMD down
    
    success "Services stopped successfully"
}

# Restart all services
restart_services() {
    log "Restarting Criticality Monitor services..."
    stop_services
    sleep 2
    start_services
}

# Show service status
show_status() {
    log "Service Status:"
    
    cd "$SCRIPT_DIR"
    $COMPOSE_CMD ps
    
    echo ""
    log "Container health:"
    docker ps --filter "name=cm-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Show logs for all or specific service
show_logs() {
    local service=${1:-}
    
    cd "$SCRIPT_DIR"
    
    if [ -z "$service" ]; then
        log "Showing logs for all services (press Ctrl+C to exit):"
        $COMPOSE_CMD logs -f
    else
        log "Showing logs for service: $service"
        $COMPOSE_CMD logs -f "$service"
    fi
}

# Update and rebuild services
update_services() {
    log "Updating Criticality Monitor services..."
    
    cd "$SCRIPT_DIR"
    
    # Pull latest changes (if this is a git repo)
    if [ -d "$PROJECT_DIR/.git" ]; then
        log "Pulling latest changes from git..."
        cd "$PROJECT_DIR"
        git pull
        cd "$SCRIPT_DIR"
    fi
    
    # Rebuild and restart
    $COMPOSE_CMD build --no-cache
    $COMPOSE_CMD up -d
    
    success "Services updated successfully"
    show_status
}

# Scale specific services
scale_service() {
    local service=$1
    local replicas=$2
    
    if [ -z "$service" ] || [ -z "$replicas" ]; then
        error "Usage: scale <service> <replicas>"
        return 1
    fi
    
    log "Scaling $service to $replicas replicas..."
    
    cd "$SCRIPT_DIR"
    $COMPOSE_CMD up -d --scale "$service=$replicas"
    
    success "Service $service scaled to $replicas replicas"
}

# Show disk usage
show_disk_usage() {
    log "Disk usage for Criticality Monitor data:"
    
    echo "Log files:"
    du -sh "$PROJECT_DIR/cm_logs" 2>/dev/null || echo "  No log directory found"
    
    echo "Generated sites:"
    du -sh "$PROJECT_DIR/site" 2>/dev/null || echo "  No site directory found"
    
    echo "Docker volumes:"
    docker system df
}

# Backup data
backup_data() {
    local backup_dir="${1:-backups/$(date +%Y%m%d_%H%M%S)}"
    
    log "Creating backup to: $backup_dir"
    
    mkdir -p "$backup_dir"
    
    # Backup logs and sites
    if [ -d "$PROJECT_DIR/cm_logs" ]; then
        cp -r "$PROJECT_DIR/cm_logs" "$backup_dir/"
    fi
    
    if [ -d "$PROJECT_DIR/site" ]; then
        cp -r "$PROJECT_DIR/site" "$backup_dir/"
    fi
    
    # Backup configuration
    if [ -d "$PROJECT_DIR/config" ]; then
        cp -r "$PROJECT_DIR/config" "$backup_dir/"
    fi
    
    success "Backup created at: $backup_dir"
}

# Clean up old data
cleanup() {
    local days=${1:-7}
    
    warning "This will remove log files older than $days days. Continue? (y/N)"
    read -r response
    
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        log "Cleanup cancelled"
        return 0
    fi
    
    log "Cleaning up files older than $days days..."
    
    # Clean old log files
    find "$PROJECT_DIR/cm_logs" -name "*.txt" -type f -mtime +$days -delete 2>/dev/null || true
    
    # Clean Docker system
    docker system prune -f
    
    success "Cleanup completed"
}

# Show help
show_help() {
    echo "Criticality Monitor Server Management Script"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  start                 Start all services"
    echo "  stop                  Stop all services"
    echo "  restart               Restart all services"
    echo "  status                Show service status"
    echo "  logs [service]        Show logs (all services or specific service)"
    echo "  update                Update and rebuild services"
    echo "  scale <service> <n>   Scale a service to n replicas"
    echo "  disk                  Show disk usage"
    echo "  backup [dir]          Backup data to directory"
    echo "  cleanup [days]        Clean up old files (default: 7 days)"
    echo "  help                  Show this help"
    echo ""
    echo "Services:"
    echo "  automated-logger      Location logging service"
    echo "  batch-processor-hamburg  Hamburg data processor"
    echo "  batch-processor-berlin   Berlin data processor"
    echo "  site-builder          Website builder"
    echo "  web-server            Nginx web server"
    echo "  monitoring            Service monitoring"
    echo ""
    echo "Examples:"
    echo "  $0 start              # Start all services"
    echo "  $0 logs web-server    # Show web server logs"
    echo "  $0 scale batch-processor-hamburg 3  # Scale Hamburg processor"
    echo "  $0 backup /backup/cm  # Backup to specific directory"
}

# Main script logic
main() {
    local command=${1:-help}
    
    # Check dependencies first
    check_dependencies
    
    case "$command" in
        start)
            start_services
            ;;
        stop)
            stop_services
            ;;
        restart)
            restart_services
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "$2"
            ;;
        update)
            update_services
            ;;
        scale)
            scale_service "$2" "$3"
            ;;
        disk)
            show_disk_usage
            ;;
        backup)
            backup_data "$2"
            ;;
        cleanup)
            cleanup "$2"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"