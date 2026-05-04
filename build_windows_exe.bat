@echo off
setlocal

cd /d "%~dp0"

echo [1/4] Instalando dependencias...
py -m pip install -r requirements.txt
py -m pip install pyinstaller

echo [2/4] Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [3/4] Gerando executavel...
py -m PyInstaller --noconfirm LeitorNotasFiscais.spec

echo [4/4] Copiando README de distribuicao...
if not exist dist\LeitorNotasFiscais mkdir dist\LeitorNotasFiscais
copy /Y README_EXECUTAVEL.md dist\LeitorNotasFiscais\README_EXECUTAVEL.md >nul

echo.
echo Build concluido!
echo Pasta de distribuicao: %cd%\dist\LeitorNotasFiscais
pause
