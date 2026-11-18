@echo off
setlocal
set "ASTERFALL_BROWSER=%~dp0..\link\build\native\Release\LINK.exe"
if not exist "%ASTERFALL_BROWSER%" goto missing_browser
start "" /D "%~dp0..\link\build\native\Release" "%ASTERFALL_BROWSER%" --open link://127.0.0.1:8002/link-game %*
exit /b %errorlevel%
:missing_browser
echo LINK Browser was not found at:
echo %ASTERFALL_BROWSER%
echo Build the current LINK Browser with shared-state-v1 and input-v1 support first.
pause
exit /b 1