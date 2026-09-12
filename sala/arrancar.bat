@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Sala DUNNE

rem ===========================================================================
rem  Arranca la sala interactiva en la laptop de DUNNE.
rem
rem  Existe para que nadie tenga que abrir una terminal ni recordar comandos
rem  el día de la exhibicion. Verifica lo que suele fallar antes de arrancar,
rem  en el orden en que conviene descartarlo.
rem ===========================================================================

cd /d "%~dp0"

echo.
echo   SALA INTERACTIVA · DUNNE
echo   ------------------------
echo.

rem --- 1. Python disponible -------------------------------------------------
where python >nul 2>nul
if errorlevel 1 (
  echo   [X] No se encontro Python en el PATH.
  echo       Instalalo desde python.org y marca "Add Python to PATH".
  echo.
  pause
  exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   [ok] Python !PYVER!

rem --- 2. Archivos de la sala ----------------------------------------------
if not exist "server.py" (
  echo   [X] Falta server.py. Corre este archivo desde la carpeta "sala".
  echo.
  pause
  exit /b 1
)
if not exist "assets\Neurona_sala.glb" (
  echo   [X] Falta assets\Neurona_sala.glb, el modelo 3D.
  echo.
  pause
  exit /b 1
)
echo   [ok] Archivos completos

rem --- 3. Regla de firewall ------------------------------------------------
rem  Sin esto Windows bloquea las conexiones entrantes de los telefonos y el
rem  sintoma es desconcertante: en la laptop funciona y en los dispositivos no.
netsh advfirewall firewall show rule name="Sala DUNNE" >nul 2>nul
if errorlevel 1 (
  echo   [!] No existe la regla de firewall "Sala DUNNE".
  echo       Sin ella los telefonos no podran conectarse.
  echo       Para crearla, cierra esto y ejecuta UNA VEZ como administrador:
  echo.
  echo       netsh advfirewall firewall add rule name="Sala DUNNE" dir=in action=allow protocol=TCP localport=8000
  echo.
) else (
  echo   [ok] Regla de firewall presente
)

rem --- 4. Direccion IP en la red ------------------------------------------
echo.
echo   Direcciones de esta laptop:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  set IP=%%a
  set IP=!IP: =!
  echo     http://!IP!:8000/n     ^(neuronas^)
  echo     http://!IP!:8000/m     ^(mural^)
)

echo.
echo   Arrancando. Deja esta ventana abierta; Ctrl+C para detener.
echo.

rem --topology y --dilation se pueden ajustar aqui de forma permanente.
python server.py --port 8000 --topology cadena --dilation 20

echo.
echo   Servidor detenido.
pause
