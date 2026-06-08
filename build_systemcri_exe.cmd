@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

%PYTHON% -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

%PYTHON% -m PyInstaller SYSTEMCRI.spec --clean --noconfirm
if errorlevel 1 exit /b 1

if exist ".env" (
  copy /Y ".env" "dist\.env" >nul
) else (
  if not exist "dist\.env" copy /Y ".env.example" "dist\.env" >nul
)

echo.
echo Listo: dist\SYSTEMCRI.exe
echo Deje dist\.env junto al exe para la conexion a Intersoftic.
endlocal
