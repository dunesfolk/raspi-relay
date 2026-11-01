@echo off
rem Send a pulse to raspi-relay.
rem Usage:  pulse.cmd [raspi_ip]
rem   pulse.cmd 192.168.1.50
rem   pulse.cmd [fd00::50]      (IPv6 addresses need square brackets)
rem If no address is given, RASPI_IP below is used.
setlocal
set "RASPI_IP=192.168.1.50"
if not "%~1"=="" set "RASPI_IP=%~1"

curl -sS -f -m 10 -X POST "http://%RASPI_IP%:8080/pulse"
if errorlevel 1 (
    echo Pulse FAILED ^(address %RASPI_IP%^)
    exit /b 1
)
exit /b 0
