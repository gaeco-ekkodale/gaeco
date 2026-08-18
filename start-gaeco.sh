#!/usr/bin/env bash
# Copyright (c) 2025 Ekkodale GmbH. All rights reserved.
#
# This file is part of the gaeco platform system.
#
# Use of this file is governed by the terms of the license
# in LICENSE.md at the root of this repository.
# Unauthorized copying, modification, distribution, or use of this file,
# via any medium, is strictly prohibited except as expressly permitted
# under that license.

# ============================================================
# start-gaeco.sh  (macOS / Linux counterpart of start-gaeco.bat)
# Starts the complete gaeco stack locally from prebuilt
# images (NO build - this repo works only with images).
#
# Flow:
#   1. Check Docker daemon + .env
#   2. Ask: clean start? (stop stack + delete volumes)
#   3. Ask: with demo data?
#   4. On clean start: down -v + delete volume folder
#   5. Stop old stack (different project name) + clean up network
#   6. Start stack (docker compose up -d, without pull)
#   7. Wait until ALL containers healthy + Keycloak realm reachable
#   8. Optional: load demo data
#   9. Open http://localhost:5000 in the browser
# ============================================================

set -uo pipefail
cd "$(dirname "$0")" || exit 1

PS_FILE="$(mktemp -t gaeco_ps.XXXXXX)"
trap 'rm -f "$PS_FILE"' EXIT

# Wait for a keypress before exiting (like the batch file's "pause").
pause() {
  echo
  read -r -n 1 -p "Press any key to continue ..." _ 2>/dev/null || read -r _
  echo
}

# Read a KEY=value from .env; strips quotes and inline "# ..." comments.
env_value() {
  local key="$1" line
  line="$(grep -i -m1 "^${key}=" .env 2>/dev/null)" || return 1
  [ -n "$line" ] || return 1
  line="${line#*=}"
  line="${line%%#*}"
  line="$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/^"\(.*\)"$/\1/' -e "s/^'\(.*\)'$/\1/")"
  [ -n "$line" ] || return 1
  printf '%s' "$line"
}

# Open a URL in the default browser (macOS / Linux).
open_url() {
  if command -v open >/dev/null 2>&1; then
    open "$1" >/dev/null 2>&1 &
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$1" >/dev/null 2>&1 &
  else
    echo "Please open $1 in your browser."
  fi
}

# === Step 1a: Is the Docker daemon running? ===
if ! docker info >/dev/null 2>&1; then
  echo "ERROR: Docker is not reachable."
  echo "        Please start Docker (Desktop / daemon) and then run again."
  pause
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: 'docker compose' (Compose V2) is not available."
  echo "        Please install the Docker Compose plugin and then run again."
  pause
  exit 1
fi

# === Step 1b: .env present? ===
if [ ! -f ".env" ]; then
  echo ".env not found - creating it from .env.example ..."
  if [ ! -f ".env.example" ]; then
    echo "ERROR: .env.example is missing - cannot create .env."
    pause
    exit 1
  fi
  cp ".env.example" ".env"
  echo
  echo "IMPORTANT: Please set the IMAGE_REGISTRY line in .env"
  echo "         (e.g. IMAGE_REGISTRY=ghcr.io/your-org)."
  echo "Then start this script again."
  pause
  exit 1
fi

# === Step 1c: Read project name from .env (default: gaeco) ===
# Compose reads COMPOSE_PROJECT_NAME from .env itself; we need the
# value here only for the network cleanup (project label comparison).
PROJECT="$(env_value COMPOSE_PROJECT_NAME || true)"
PROJECT="${PROJECT:-gaeco}"

echo "============================================================"
echo "  gaeco - local start (images only, no build)"
echo "  Docker project: $PROJECT"
echo "============================================================"
echo

# === Step 2: Ask for clean start ===
echo "WARNING: A clean start deletes ALL local data"
echo "         (databases, MinIO, Keycloak users, ...)."
read -r -p "Clean start? Stop the stack and delete all volumes? (Y/N): " CLEAN
CLEAN="${CLEAN:0:1}"
echo

# === Step 3: Ask for demo data ===
read -r -p "Start with demo data? (Y/N): " DEMO
DEMO="${DEMO:0:1}"
echo

# === Step 4: On clean start, stop stack + delete volumes ===
if [ "$CLEAN" = "Y" ] || [ "$CLEAN" = "y" ]; then
  echo "Stopping stack and removing containers/volumes ..."
  docker compose down -v --remove-orphans
  if [ -d "volumes" ]; then
    echo "Deleting volume folder: $(pwd)/volumes"
    if rm -rf "volumes" 2>/dev/null; then
      echo "Volumes deleted."
    else
      # On Linux container files often belong to root -> plain rm fails.
      echo "WARN: Volume folder could not be deleted without elevated rights."
      echo "      Trying with sudo ..."
      if sudo rm -rf "volumes"; then
        echo "Volumes deleted."
      else
        echo "ERROR: Volume folder could not be deleted. Please remove"
        echo "       $(pwd)/volumes manually and run again."
        pause
        exit 1
      fi
    fi
  else
    echo "No volume folder found - skipped."
  fi
  echo
else
  echo "Existing volumes are preserved."
  echo
fi

# === Step 5: Clean up old stack under different project name + network ===
# The Compose network is named "gaeco-local" (key: gaeco-network). If a
# stack is still running under a DIFFERENT project name (e.g. the previously used "gaeco-ext"),
# it occupies the same ports/networks -> "docker compose up" under "$PROJECT" would
# collide. We stop such an old stack first and then remove the network;
# Compose then recreates it correctly for "$PROJECT".
NET_PROJECT="$(docker network inspect gaeco-local --format '{{index .Labels "com.docker.compose.project"}}' 2>/dev/null || true)"
if [ -n "$NET_PROJECT" ] && [ "$(printf '%s' "$NET_PROJECT" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$PROJECT" | tr '[:upper:]' '[:lower:]')" ]; then
  echo "A stack is still running under old project name \"$NET_PROJECT\"."
  echo "It will be stopped so \"$PROJECT\" can occupy the ports/networks ..."
  if [ "$CLEAN" = "Y" ] || [ "$CLEAN" = "y" ]; then
    docker compose -p "$NET_PROJECT" down -v --remove-orphans
  else
    docker compose -p "$NET_PROJECT" down --remove-orphans
  fi
  if ! docker network rm gaeco-local >/dev/null 2>&1; then
    echo "WARN: Network gaeco-local could not be removed."
    echo "      Please choose clean start or check Docker."
  fi
  echo
fi

# === Step 6: Start stack (without pull - images are available locally) ===
echo "Starting stack (docker compose up -d --pull never) ..."
echo
docker compose up -d --pull never --remove-orphans
DC_EXIT=$?
echo

if [ "$DC_EXIT" -ne 0 ]; then
  echo "============================================================"
  echo "ERROR: \"docker compose up\" aborted with exit code $DC_EXIT."
  echo "        Probably NO containers were started."
  echo "============================================================"
  echo
  echo "Current state:"
  docker compose ps -a
  echo
  echo "Next steps:"
  echo "  - View logs:   docker compose logs <service>"
  echo "  - On \"network ... incorrect label\": run this script with clean start."
  echo "  - Missing an image? Check \"docker images\" (this repo deliberately does not pull)."
  pause
  exit 1
fi

# === Step 7: Wait until all containers healthy + Keycloak reachable ===
# Read KEYCLOAK_PORT / KEYCLOAK_REALM from .env (defaults as fallback).
KEYCLOAK_PORT="$(env_value KEYCLOAK_PORT || true)"
KEYCLOAK_PORT="${KEYCLOAK_PORT:-9345}"
KEYCLOAK_REALM="$(env_value KEYCLOAK_REALM || true)"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-gaeco}"

echo "Waiting until ALL containers are healthy - up to 300s ..."
WAIT_TRIES=0
HEALTH_TIMEOUT=0

while :; do
  docker compose ps -a --format '{{.Service}}: {{.Status}}' > "$PS_FILE" 2>/dev/null

  # (a) Hard errors -> abort immediately.
  if grep -i -E 'unhealthy|Exited|Restarting' "$PS_FILE" >/dev/null 2>&1; then
    echo
    echo "ERROR: At least one container did not become healthy:"
    grep -i -E 'unhealthy|Exited|Restarting' "$PS_FILE"
    echo
    echo "Check logs: docker compose logs <service>"
    pause
    exit 1
  fi

  # (b) Are there any containers at all?  (Empty output = up created nothing.)
  if [ ! -s "$PS_FILE" ]; then
    echo "ERROR: No containers present - start failed."
    docker compose ps -a
    pause
    exit 1
  fi

  # (c) Still something starting up?  (Created / health: starting)
  if grep -i -E 'health: starting|Created' "$PS_FILE" >/dev/null 2>&1; then
    WAIT_TRIES=$((WAIT_TRIES + 1))
    if [ "$WAIT_TRIES" -ge 60 ]; then
      HEALTH_TIMEOUT=1
      break
    fi
    sleep 5
    continue
  fi

  break
done

if [ "$HEALTH_TIMEOUT" -eq 1 ]; then
  echo
  echo "WARN: Not all containers became healthy after 300s. State:"
  docker compose ps -a
  echo
  echo "The stack may still be starting up. Browser will NOT be"
  echo "opened automatically - open http://localhost:5000 yourself later."
  pause
  exit 1
fi

# All containers healthy -> now check Keycloak reachability from the host.
KC_URL="http://localhost:${KEYCLOAK_PORT}/realms/${KEYCLOAK_REALM}"
echo "All containers healthy. Checking Keycloak: $KC_URL ..."
KC_TRIES=0
KC_OK=0
while :; do
  if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$KC_URL" 2>/dev/null)" = "200" ]; then
    KC_OK=1
    break
  fi
  KC_TRIES=$((KC_TRIES + 1))
  if [ "$KC_TRIES" -ge 24 ]; then
    break
  fi
  sleep 5
done

if [ "$KC_OK" -ne 1 ]; then
  echo
  echo "WARN: Keycloak realm '$KEYCLOAK_REALM' was not reachable after 120s."
  echo "      The stack may still be running. Browser will NOT be opened automatically."
  echo "      Check later: $KC_URL"
  pause
  exit 1
fi

echo "Success: Stack healthy and Keycloak realm '$KEYCLOAK_REALM' reachable."
echo

# === Step 8: Load demo data ===
if [ "$DEMO" = "Y" ] || [ "$DEMO" = "y" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PY=python3
  elif command -v python >/dev/null 2>&1; then
    PY=python
  else
    PY=""
  fi
  if [ -z "$PY" ]; then
    echo "WARN: Python not found - demo data will be skipped."
    echo "      Load later with:  python3 demodata/setup-demo-data.py"
  else
    echo "Loading demo data ..."
    "$PY" demodata/setup-demo-data.py
  fi
  echo
fi

# === Step 9: Open app in browser ===
echo "Opening http://localhost:5000 in the browser ..."
open_url "http://localhost:5000"

echo
echo "Done."
if [ "$CLEAN" = "Y" ] || [ "$CLEAN" = "y" ]; then
  echo
  echo "After a clean start, log in to the Plugin Host with the demo user:"
  echo "    username: admin"
  echo "    password: admin"
fi
pause
exit 0
