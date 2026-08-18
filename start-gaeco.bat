@echo off
REM Copyright (c) 2025 Ekkodale GmbH. All rights reserved.
REM
REM This file is part of the gaeco platform system.
REM
REM Use of this file is governed by the terms of the license
REM in LICENSE.md at the root of this repository.
REM Unauthorized copying, modification, distribution, or use of this file,
REM via any medium, is strictly prohibited except as expressly permitted
REM under that license.

setlocal enabledelayedexpansion
cd /d "%~dp0"
title gaeco - local start

REM ============================================================
REM start-gaeco.bat
REM Starts the complete gaeco stack locally from prebuilt
REM images (NO build - this repo works only with images).
REM
REM Flow:
REM   1. Check Docker daemon + .env
REM   2. Ask: clean start? (stop stack + delete volumes)
REM   3. Ask: with demo data?
REM   4. On clean start: down -v + delete volume folder
REM   5. Stop old stack (different project name) + clean up network
REM   6. Always pull the latest images, then start the stack
REM   7. Wait until ALL containers healthy + Keycloak realm reachable
REM   8. Optional: load demo data
REM   9. Open http://localhost:5000 in the browser
REM ============================================================

REM === Step 1a: Is the Docker daemon running? ===
docker info >nul 2>nul
if errorlevel 1 (
  echo ERROR: Docker is not reachable.
  echo         Please start Docker Desktop and then run again.
  echo.
  pause
  goto :EOF
)

REM === Step 1b: .env present? ===
if not exist ".env" (
  echo .env not found - creating it from .env.example ...
  copy /y ".env.example" ".env" >nul
  echo.
  echo IMPORTANT: Please set the IMAGE_REGISTRY line in .env
  echo          ^(e.g. IMAGE_REGISTRY=ghcr.io/your-org^).
  echo Then start this script again.
  echo.
  pause
  goto :EOF
)

REM === Step 1c: Read project name from .env (default: gaeco) ===
REM Compose reads COMPOSE_PROJECT_NAME from .env itself; we need the
REM value here only for the network cleanup (project label comparison).
set "PROJECT=gaeco"
for /f "usebackq tokens=1,2 delims== " %%A in (`findstr /b /i /c:"COMPOSE_PROJECT_NAME=" ".env"`) do set "PROJECT=%%B"

echo ============================================================
echo   gaeco - local start ^(images only, no build^)
echo   Docker project: %PROJECT%
echo ============================================================
echo.

REM === Step 2: Ask for clean start ===
echo WARNING: A clean start deletes ALL local data
echo          ^(databases, MinIO, Keycloak users, ...^).
set /p CLEAN=Clean start? Stop the stack and delete all volumes? (Y/N):
set "CLEAN=%CLEAN:~0,1%"
echo.

REM === Step 3: Ask for demo data ===
set /p DEMO=Start with demo data? (Y/N):
set "DEMO=%DEMO:~0,1%"
echo.

REM === Step 4: On clean start, stop stack + delete volumes ===
if /i "%CLEAN%"=="Y" (
  echo Stopping stack and removing containers/volumes ...
  docker compose down -v --remove-orphans
  if exist "volumes" (
    echo Deleting volume folder: %~dp0volumes
    rmdir /s /q "volumes"
    echo Volumes deleted.
  ) else (
    echo No volume folder found - skipped.
  )
  echo.
) else (
  echo Existing volumes are preserved.
  echo.
)

REM === Step 5: Clean up old stack under different project name + network ===
REM The Compose network is named "gaeco-local" (key: gaeco-network). If a
REM stack is still running under a DIFFERENT project name (e.g. the previously used "gaeco-ext"),
REM it occupies the same ports/networks -> "docker compose up" under "%PROJECT%" would
REM collide. We stop such an old stack first and then remove the network;
REM Compose then recreates it correctly for "%PROJECT%".
set "NET_PROJECT="
for /f "delims=" %%L in ('docker network inspect gaeco-local --format "{{index .Labels \"com.docker.compose.project\"}}" 2^>nul') do set "NET_PROJECT=%%L"
if defined NET_PROJECT if /i not "!NET_PROJECT!"=="%PROJECT%" (
  echo A stack is still running under old project name "!NET_PROJECT!".
  echo It will be stopped so "%PROJECT%" can occupy the ports/networks ...
  if /i "%CLEAN%"=="Y" (
    docker compose -p "!NET_PROJECT!" down -v --remove-orphans
  ) else (
    docker compose -p "!NET_PROJECT!" down --remove-orphans
  )
  docker network rm gaeco-local >nul 2>nul
  if errorlevel 1 (
    echo WARN: Network gaeco-local could not be removed.
    echo       Please choose clean start or check Docker Desktop.
  )
  echo.
)

REM === Step 6a: Always pull the latest images ===
echo Pulling latest images ^(docker compose pull^) ...
echo.
docker compose pull
if errorlevel 1 (
  echo.
  echo WARN: "docker compose pull" failed ^(no registry login / offline?^).
  echo       Continuing with the locally available images.
  echo       Login if needed:  docker login ^<registry^>
  echo.
)

REM === Step 6b: Start stack ===
echo Starting stack ^(docker compose up -d^) ...
echo.
docker compose up -d --remove-orphans
set "DC_EXIT=%ERRORLEVEL%"
echo.

if not "%DC_EXIT%"=="0" (
  echo ============================================================
  echo ERROR: "docker compose up" aborted with exit code %DC_EXIT%.
  echo         Probably NO containers were started.
  echo ============================================================
  echo.
  echo Current state:
  docker compose ps -a
  echo.
  echo Next steps:
  echo   - View logs:   docker compose logs ^<service^>
  echo   - On "network ... incorrect label": run this script with clean start.
  echo   - Missing an image? Check "docker images" and the registry login.
  echo.
  pause
  goto :EOF
)

REM === Step 7: Wait until all containers healthy + Keycloak reachable ===
REM Read KEYCLOAK_PORT / KEYCLOAK_REALM from .env (defaults as fallback).
REM tokens=1,2 delims=<equals sign><space> strips inline
REM comments (# ...) after the value.
set "KEYCLOAK_PORT=9345"
set "KEYCLOAK_REALM=gaeco"
for /f "usebackq tokens=1,2 delims== " %%A in (`findstr /b /i /c:"KEYCLOAK_PORT=" ".env"`) do set "KEYCLOAK_PORT=%%B"
for /f "usebackq tokens=1,2 delims== " %%A in (`findstr /b /i /c:"KEYCLOAK_REALM=" ".env"`) do set "KEYCLOAK_REALM=%%B"

echo Waiting until ALL containers are healthy - up to 300s ...
set /a WAIT_TRIES=0
:health_loop
docker compose ps -a --format "{{.Service}}: {{.Status}}" > "%TEMP%\gaeco_ps.txt" 2>nul

REM (a) Hard errors -> abort immediately.
findstr /i /c:"unhealthy" /c:"Exited" /c:"Restarting" "%TEMP%\gaeco_ps.txt" >nul && (
  echo.
  echo ERROR: At least one container did not become healthy:
  findstr /i /c:"unhealthy" /c:"Exited" /c:"Restarting" "%TEMP%\gaeco_ps.txt"
  echo.
  echo Check logs: docker compose logs ^<service^>
  pause
  goto :EOF
)

REM (b) Are there any containers at all?  (Empty output = up created nothing.)
for %%S in ("%TEMP%\gaeco_ps.txt") do if %%~zS EQU 0 (
  echo ERROR: No containers present - start failed.
  docker compose ps -a
  pause
  goto :EOF
)

REM (c) Still something starting up?  (Created / health: starting)
findstr /i /c:"health: starting" /c:"Created" "%TEMP%\gaeco_ps.txt" >nul
if not errorlevel 1 (
  set /a WAIT_TRIES+=1
  if !WAIT_TRIES! GEQ 60 goto health_timeout
  timeout /t 5 /nobreak >nul
  goto health_loop
)

REM All containers healthy -> now check Keycloak reachability from the host.
echo All containers healthy. Checking Keycloak: http://localhost:!KEYCLOAK_PORT!/realms/!KEYCLOAK_REALM! ...
set /a KC_TRIES=0
:kc_loop
powershell -NoProfile -Command "try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 -Uri 'http://localhost:!KEYCLOAK_PORT!/realms/!KEYCLOAK_REALM!').StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if not errorlevel 1 goto started
set /a KC_TRIES+=1
if !KC_TRIES! GEQ 24 goto kc_timeout
timeout /t 5 /nobreak >nul
goto kc_loop

:kc_timeout
echo.
echo WARN: Keycloak realm '!KEYCLOAK_REALM!' was not reachable after 120s.
echo       The stack may still be running. Browser will NOT be opened automatically.
echo       Check later: http://localhost:!KEYCLOAK_PORT!/realms/!KEYCLOAK_REALM!
echo.
pause
goto :EOF

:health_timeout
echo.
echo WARN: Not all containers became healthy after 300s. State:
docker compose ps -a
echo.
echo The stack may still be starting up. Browser will NOT be
echo opened automatically - open http://localhost:5000 yourself later.
echo.
pause
goto :EOF

:started
echo Success: Stack healthy and Keycloak realm '!KEYCLOAK_REALM!' reachable.
echo.

REM === Step 8: Load demo data ===
if /i "%DEMO%"=="Y" (
  where python >nul 2>nul
  if errorlevel 1 (
    echo WARN: Python not found - demo data will be skipped.
    echo       Load later with:  python demodata\setup-demo-data.py
  ) else (
    echo Loading demo data ...
    python demodata\setup-demo-data.py
  )
  echo.
)

REM === Step 9: Open app in browser ===
echo Opening http://localhost:5000 in the browser ...
start "" "http://localhost:5000"

echo.
echo Done.
if /i "%CLEAN%"=="Y" (
  echo.
  echo After a clean start, log in to the Plugin Host with the demo user:
  echo     username: admin
  echo     password: admin
)
echo.
pause
goto :EOF
