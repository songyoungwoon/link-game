@echo off
setlocal
where py >nul 2>&1
if errorlevel 1 goto check_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto check_python
py -3 "%~dp0tools\run_npc_demo.py" %*
set "LINK_NPC_EXIT=%errorlevel%"
goto finished
:check_python
where python >nul 2>&1
if errorlevel 1 goto missing_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto missing_python
python "%~dp0tools\run_npc_demo.py" %*
set "LINK_NPC_EXIT=%errorlevel%"
goto finished
:missing_python
echo LINK NPC demo requires Python 3.10 or newer.
echo Install Python from https://www.python.org/downloads/windows/ and retry.
set "LINK_NPC_EXIT=1"
:finished
if not "%LINK_NPC_EXIT%"=="0" pause
exit /b %LINK_NPC_EXIT%