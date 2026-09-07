@echo off
chcp 65001 >nul
:: Проверка прав администратора
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ТРЕБУЮТСЯ ПРАВА АДМИНИСТРАТОРА]
    echo Пожалуйста, запустите этот файл от имени Администратора:
    echo Правой кнопкой мыши -^> Запуск от имени администратора.
    echo.
    pause
    exit /b 1
)

echo.
echo =====================================================================
echo   Настройка брандмауэра Windows Server 2025 для «Календарь ТО»
echo =====================================================================
echo.
echo Открытие входящего TCP-порта 9000 для локальной сети...
netsh advfirewall firewall add rule name="Kalendar_TO_Port_9000" dir=in action=allow protocol=TCP localport=9000 profile=any

if %errorlevel% equ 0 (
    echo.
    echo [УСПЕХ] Порт 9000 успешно открыт в брандмауэре Windows.
    echo Теперь система доступна для рабочих мест по адресу:
    echo http://^<IP_АДРЕС_СЕРВЕРА^>:9000
) else (
    echo.
    echo [ОШИБКА] Не удалось добавить правило брандмауэра.
)

echo.
pause
