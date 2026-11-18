@echo off
setlocal
set "LINK_NPC_BROWSER=%~dp0..\link\build\native\Release\LINK.exe"
if not exist "%LINK_NPC_BROWSER%" goto missing_browser
start "" /D "%~dp0..\link\build\native\Release" "%LINK_NPC_BROWSER%" --open link://127.0.0.1:8010/traveler-a %*
exit /b %errorlevel%
:missing_browser
echo Build the latest LINK Browser with npc-travel-v1 support first.
pause
exit /b 1
