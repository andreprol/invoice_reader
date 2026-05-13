@echo off
setlocal enabledelayedexpansion

echo.
echo ============================================
echo  Adicionar Poppler ao PATH do Windows
echo ============================================
echo.

set "APP_DIR=%~dp0"
set "POPPLER_BIN="

:: Procurar pasta poppler na pasta do app
if exist "%APP_DIR%poppler\Library\bin\pdftoppm.exe" (
    set "POPPLER_BIN=%APP_DIR%poppler\Library\bin"
) else if exist "%APP_DIR%poppler\bin\pdftoppm.exe" (
    set "POPPLER_BIN=%APP_DIR%poppler\bin"
)

:: Procurar em locais comuns
if "!POPPLER_BIN!"=="" (
    if exist "C:\poppler\Library\bin\pdftoppm.exe" set "POPPLER_BIN=C:\poppler\Library\bin"
    if exist "C:\poppler\bin\pdftoppm.exe" set "POPPLER_BIN=C:\poppler\bin"
)

:: Buscar subpastas poppler-*
if "!POPPLER_BIN!"=="" (
    for /d %%D in ("%APP_DIR%poppler-*") do (
        if exist "%%D\Library\bin\pdftoppm.exe" set "POPPLER_BIN=%%D\Library\bin"
        if exist "%%D\bin\pdftoppm.exe" set "POPPLER_BIN=%%D\bin"
    )
)

if "!POPPLER_BIN!"=="" (
    echo [ERRO] Poppler nao foi encontrado!
    echo.
    echo Execute primeiro: instalar_poppler.bat
    echo.
    pause
    exit /b 1
)

echo Poppler encontrado em:
echo   !POPPLER_BIN!
echo.

:: Verificar se ja esta no PATH
echo %PATH% | findstr /I /C:"!POPPLER_BIN!" >nul
if %errorlevel% equ 0 (
    echo [OK] Poppler ja esta no PATH desta sessao.
)

:: Adicionar ao PATH do usuario permanentemente
echo Adicionando ao PATH do usuario (permanente)...
echo.

for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul') do set "USER_PATH=%%B"

if "!USER_PATH!"=="" (
    setx PATH "!POPPLER_BIN!"
) else (
    echo !USER_PATH! | findstr /I /C:"!POPPLER_BIN!" >nul
    if !errorlevel! equ 0 (
        echo [OK] Ja esta no PATH do usuario.
    ) else (
        setx PATH "!USER_PATH!;!POPPLER_BIN!"
    )
)

echo.
echo ============================================
echo  Concluido!
echo ============================================
echo.
echo IMPORTANTE:
echo  1. FECHE o Leitor de Notas Fiscais se estiver aberto
echo  2. Abra-o novamente (clique duplo no .exe)
echo  3. Agora o OCR deve funcionar
echo.
echo Se ainda nao funcionar, reinicie o computador.
echo.
pause
