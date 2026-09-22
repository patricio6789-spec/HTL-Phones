@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 scripts\actualizar.py
if errorlevel 1 goto failed
py -3 scripts\embeber.py
if errorlevel 1 goto failed
py -3 scripts\publicar.py
if errorlevel 1 goto failed
goto success
:try_python
where python >nul 2>nul
if errorlevel 1 goto no_python
python scripts\actualizar.py
if errorlevel 1 goto failed
python scripts\embeber.py
if errorlevel 1 goto failed
python scripts\publicar.py
if errorlevel 1 goto failed
:success
echo.
echo Catalogo y panel actualizados. Abri index.html para ver el resultado.
pause
exit /b 0
:no_python
echo Necesitas Python 3.10 o posterior, disponible en python.org.
pause
exit /b 1
:failed
echo.
echo La actualizacion no se completo. Revisa el mensaje anterior.
pause
exit /b 1
