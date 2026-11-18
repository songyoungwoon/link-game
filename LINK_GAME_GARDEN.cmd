@echo off
setlocal
set "LINK_GARDEN_BROWSER=%~dp0..\link\build\native\Release\LINK.exe"
if not exist "%LINK_GARDEN_BROWSER%" goto missing_browser
start "" /D "%~dp0..\link\build\native\Release" "%LINK_GARDEN_BROWSER%" --open link://127.0.0.1:8002/moon-garden %*
exit /b %errorlevel%
:missing_browser
echo Build the latest LINK Browser with models-v1 support first.
pause
exit /b 1
