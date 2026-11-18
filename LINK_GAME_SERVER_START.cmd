@echo off
setlocal
where py >nul 2>&1
if errorlevel 1 goto check_python
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto check_python
py -3 "%~dp0server\asterfall.py" %*
set "ASTERFALL_EXIT=%errorlevel%"
goto finished
:check_python
where python >nul 2>&1
if errorlevel 1 goto missing_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
if errorlevel 1 goto missing_python
python "%~dp0server\asterfall.py" %*
set "ASTERFALL_EXIT=%errorlevel%"
goto finished
:missing_python
echo ASTERFALL server requires Python 3.10 or newer.
echo Install Python from https://www.python.org/downloads/windows/ and retry.
set "ASTERFALL_EXIT=1"
:finished
if not "%ASTERFALL_EXIT%"=="0" pause
exit /b %ASTERFALL_EXIT%