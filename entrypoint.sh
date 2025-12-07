#!/usr/bin/env bash
set -euo pipefail

APP_USER="appuser"
APP_GROUP="appuser"
APP_UID="1000"
APP_GID="1000"

# Allow override via env
APP_USER=${APP_USER_OVERRIDE:-$APP_USER}
APP_GROUP=${APP_GROUP_OVERRIDE:-$APP_GROUP}
APP_UID=${APP_UID_OVERRIDE:-$APP_UID}
APP_GID=${APP_GID_OVERRIDE:-$APP_GID}

log() { echo "[entrypoint] $*"; }
warn() { echo "[entrypoint][WARN] $*" >&2; }

if [ "${PERM_DEBUG:-0}" = "1" ]; then
  set -x
fi

# Ensure user & group exist (in case base image changes)
if ! getent group "$APP_GROUP" >/dev/null 2>&1; then
  groupadd -g "$APP_GID" "$APP_GROUP" || warn "Could not create group $APP_GROUP"
fi
if ! id -u "$APP_USER" >/dev/null 2>&1; then
  useradd -m -u "$APP_UID" -g "$APP_GROUP" -s /bin/bash "$APP_USER" || warn "Could not create user $APP_USER"
fi

ensure_dir() {
  local d="$1"
  [ -z "$d" ] && return 0
  if [ ! -d "$d" ]; then
    mkdir -p "$d" || { warn "Failed to create $d"; return 0; }
  fi
  if chown "$APP_USER:$APP_GROUP" "$d" 2>/dev/null; then
    chmod 0775 "$d" || warn "Failed to chmod $d"
  else
    warn "Could not chown $d; relaxing permissions"
    chmod g+rwxs "$d" || warn "Failed to chmod (fallback) $d"
  fi
}

# Base required dirs
BASE_DIRS="/app/data/site /app/data/logs"

# Discover cities dynamically
# Priority order:
# 1. CITIES env var (comma or space separated)
# 2. EXTRA_CITY_DIRS env var (appended)
# 3. Parse --city <name> and --primary-city <name> from arguments
RAW_CITIES="${CITIES:-} ${EXTRA_CITY_DIRS:-}"
if [ -z "$RAW_CITIES" ]; then
  # Parse args for flags
  next_is_city=""
  for arg in "$@"; do
    if [ "$next_is_city" = "1" ]; then
      RAW_CITIES="$RAW_CITIES $arg"
      next_is_city=""
      continue
    fi
    case "$arg" in
      --city|--primary-city)
        next_is_city=1
        ;;
    esac
  done
fi

# Normalize: split on commas and spaces, filter
CITY_DIRS=""
IFS=' ,\n' read -r -a city_array <<EOF
$RAW_CITIES
EOF
for c in "${city_array[@]}"; do
  [ -z "$c" ] && continue
  # Sanitize: allow alnum, dash, underscore only
  clean=$(echo "$c" | tr -cd '[:alnum:]_-')
  [ -z "$clean" ] && continue
  CITY_DIRS="$CITY_DIRS /app/data/sites/$clean"
done

log "Detected city directories: ${CITY_DIRS:-<none>}"

for d in $BASE_DIRS $CITY_DIRS; do
  ensure_dir "$d"
done

# Debug: show directory ownership & perms if requested
if [ "${PERM_DEBUG:-0}" = "1" ]; then
  log "Directory status after ensure_dir:"
  for d in $BASE_DIRS $CITY_DIRS; do
    [ -d "$d" ] && ls -ld "$d"
  done
fi

# Targeted recursive fix for logs (avoid large chown trees)
if [ -d /app/data/logs ]; then
  if chown -R "$APP_USER:$APP_GROUP" /app/data/logs 2>/dev/null; then
    chmod -R g+rw /app/data/logs || true
  fi
fi

if [ "$(id -u)" != "0" ]; then
  warn "Entrypoint is NOT running as root (current uid: $(id -u)). If directories are root-owned bind mounts, permission fixes may fail. Remove 'user:' override in docker-compose for automatic permission management, or pre-chown host directories."
fi

log "Starting as $APP_USER (uid:$(id -u $APP_USER))"
exec gosu "$APP_USER" "$@"
