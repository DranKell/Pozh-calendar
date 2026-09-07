@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo =====================================================================
echo   Установка компонентов «Календарь ТО»
echo =====================================================================
echo.

:: -----------------------------------------------------------------------
:: Шаг 0: Проверка наличия Python в системе
:: -----------------------------------------------------------------------
set "PY_CMD="

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py"
    )
)

if defined PY_CMD (
    echo [OK] Python обнаружен в системе:
    %PY_CMD% --version
    goto :PYTHON_READY
)

:: -----------------------------------------------------------------------
:: Если Python не найден — автоматическая загрузка и установка
:: -----------------------------------------------------------------------
echo [!] Python не найден в системе.
echo [*] Запуск автоматической загрузки и установки Python 3.11 для Windows Server...
echo.

set "INSTALLER_NAME=python-3.11.9-amd64.exe"
set "INSTALLER_PATH=%TEMP%\%INSTALLER_NAME%"
set "PY_URL=https://www.python.org/ftp/python/3.11.9/%INSTALLER_NAME%"

echo [0/3] Скачивание официального установщика Python 3.11.9...
curl.exe -L --fail --show-error "%PY_URL%" -o "%INSTALLER_PATH%"
if %errorlevel% neq 0 (
    echo.
    echo [*] Попытка скачивания через PowerShell...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%PY_URL%', '%INSTALLER_PATH%')"
)

if not exist "%INSTALLER_PATH%" (
    echo.
    echo [ОШИБКА] Не удалось скачать установщик Python.
    echo Проверьте подключение к сети Интернет или установите Python вручную:
    echo https://www.python.org/downloads/
    echo Обязательно отметьте галочку "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

echo.
echo [0/3] Установка Python с автоматическим добавлением в переменную PATH...
echo (Пожалуйста, подождите 1-2 минуты, процесс выполняется в фоновом режиме...)
"%INSTALLER_PATH%" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0 Shortcuts=0
set "INSTALL_STATUS=%errorlevel%"

:: Удаляем временный установщик
if exist "%INSTALLER_PATH%" del /f /q "%INSTALLER_PATH%" >nul 2>&1

:: Обновляем переменные окружения текущей сессии
for /f "tokens=2* delims= " %%a in ('reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path 2^>nul') do set "SYS_PATH=%%b"
for /f "tokens=2* delims= " %%a in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%b"
set "PATH=%SYS_PATH%;%USER_PATH%;%ProgramFiles%\Python311;%ProgramFiles%\Python311\Scripts;%LocalAppData%\Programs\Python\Python311;%LocalAppData%\Programs\Python\Python311\Scripts;%PATH%"

set "PY_CMD="
where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else if exist "%ProgramFiles%\Python311\python.exe" (
    set "PY_CMD="%ProgramFiles%\Python311\python.exe""
) else if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
    set "PY_CMD="%LocalAppData%\Programs\Python\Python311\python.exe""
)

if not defined PY_CMD (
    echo.
    echo [!] Установка завершена, но для применения PATH в командной строке
    echo     может потребоваться перезапустить окно терминала или систему.
    echo     Попробуйте запустить install.bat повторно в новом окне.
    echo.
    pause
    exit /b 1
)

echo.
echo [УСПЕХ] Python успешно установлен:
%PY_CMD% --version

:PYTHON_READY
echo.
echo ---------------------------------------------------------------------
echo [1/3] Обновление менеджера пакетов pip...
%PY_CMD% -m pip install --upgrade pip --retries 5 --timeout 30

echo.
echo [2/3] Установка необходимых библиотек из requirements.txt...
%PY_CMD% -m pip install --prefer-binary -r requirements.txt --retries 5 --timeout 30

if %errorlevel% neq 0 (
    echo.
    echo [ПРЕДУПРЕЖДЕНИЕ] Стандартный индекс недоступен. Пробуем быстрое зеркало...
    %PY_CMD% -m pip install --prefer-binary -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
)

echo.
echo [3/3] Проверка и инициализация базы данных и справочника (seed.py)...
%PY_CMD% seed.py

echo.
echo =====================================================================
echo   Все компоненты системы «Календарь ТО» успешно настроены!
echo.
echo   Для запуска системы:
echo   - используйте run.bat или команду: %PY_CMD% run.py
echo   - для разрешения доступа по сети запустите: open_firewall_port.bat
echo =====================================================================
echo.
pause
