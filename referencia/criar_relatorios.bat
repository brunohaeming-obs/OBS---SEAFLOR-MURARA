@echo on
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "YEAR=%~1"
if "%YEAR%"=="" set "YEAR=2025"
set "MONTH=%~2"
set "MONTH_ARG="
if not "%MONTH%"=="" set "MONTH_ARG=--ref-month %MONTH%"

set "SCRIPT=Scripts\datamarts.py"
set "CATS=categorias.txt"
if not exist "%CATS%" if exist "Scripts\categorias.txt" set "CATS=Scripts\categorias.txt"
set "LOG=last_run.log"

if not exist "%SCRIPT%" ( echo [FATAL] %SCRIPT% not found & pause & exit /b 1 )
if not exist "%CATS%"   ( echo [FATAL] categorias.txt not found & pause & exit /b 1 )

REM --- Find Python (most robust order) ---
set "PY="
for %%P in (
  ".venv\Scripts\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
  "%ProgramFiles%\Python313\python.exe"
  "%ProgramFiles%\Python312\python.exe"
  "%ProgramFiles%\Python311\python.exe"
) do (
  if exist "%%~fP" set "PY=%%~fP" & goto :have_py
)

REM Try Windows Python launcher
if exist "%SystemRoot%\py.exe" (
  set "PY=%SystemRoot%\py.exe -3"
  goto :have_py
)

echo [FATAL] No Python found. Edit criar_relatorios.bat and set PY to your python.exe full path.
pause
exit /b 1

:have_py
echo ===== RUN %DATE% %TIME% ===== > "%LOG%"
echo [INFO] Using: %PY% >> "%LOG%"
echo [INFO] Cmd  : %PY% %SCRIPT% all --sc-file "%CATS%" --each --ref-year %YEAR% %MONTH_ARG% >> "%LOG%"
%PY% %SCRIPT% all --sc-file "%CATS%" --each --ref-year %YEAR% %MONTH_ARG% 1>>"%LOG%" 2>&1
echo [INFO] Exit code: %ERRORLEVEL%
echo [INFO] Log: %CD%\%LOG%
pause
endlocal