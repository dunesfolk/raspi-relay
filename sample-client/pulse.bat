@echo off
chcp 65001 >nul
setlocal

set "URL=http://192.168.50.100:8080/pulse"
set "RESP=%TEMP%\pulse_resp_%RANDOM%.txt"

rem Send the request. -m 5 = give up after 5 seconds.
curl.exe -s -m 5 -X POST "%URL%" -o "%RESP%"
if errorlevel 1 goto noresponse

findstr /R /C:"\"result\": *\"ok\"" "%RESP%" >nul && goto ok
findstr /R /C:"\"result\": *\"busy\"" "%RESP%" >nul && goto busy
goto unexpected

:ok
echo 開錠しました
del "%RESP%" >nul 2>&1
timeout /t 5 /nobreak >nul
exit /b 0

:busy
echo 既に開錠中です
del "%RESP%" >nul 2>&1
timeout /t 5 /nobreak >nul
exit /b 0

:noresponse
echo エラー：応答がありませんでした
del "%RESP%" >nul 2>&1
timeout /t 10 /nobreak >nul
exit /b 1

:unexpected
echo エラー：予期しない応答です
type "%RESP%"
echo.
del "%RESP%" >nul 2>&1
timeout /t 10 /nobreak >nul
exit /b 1
