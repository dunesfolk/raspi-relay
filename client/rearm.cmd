@echo off
rem End a running break now (reconnect the circuit).
rem Usage:  rearm.cmd [raspi_ip]
rem   rearm.cmd 192.168.1.50
rem   rearm.cmd [fd00::50]      (IPv6 addresses need square brackets)
rem If no address is given, RASPI_IP below is used.
setlocal
set "RASPI_IP=192.168.1.50"
if not "%~1"=="" set "RASPI_IP=%~1"

curl -sS -f -m 10 -X POST "http://%RASPI_IP%:8080/rearm"
if errorlevel 1 (
    echo Rearm FAILED ^(address %RASPI_IP%^)
    exit /b 1
)
exit /b 0
