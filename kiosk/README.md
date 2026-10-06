# Киоск-режим Windows 11 Pro

Эта настройка предназначена только для отдельной локальной учётной записи `ProctorKiosk`. Не назначай киоск своей основной или администраторской учётной записи.

## 1. Собери приложение

Из папки проекта запусти PowerShell-скрипт `build_windows.ps1`. Он создаст `dist\QostanaiProctor.zip`. Распакуй содержимое архива в `C:\QostanaiProctor`. Проверь, что там есть `QostanaiProctor.exe` и `yolov8n.pt`.

## 2. Создай отдельного пользователя

В Windows открой **Параметры → Учётные записи → Другие пользователи → Добавить учётную запись**. Выбери создание пользователя без учётной записи Microsoft и назови его `ProctorKiosk`. Оставь его обычным пользователем, не администратором. Подробности — в [инструкции Microsoft по учётным записям](https://support.microsoft.com/en-us/windows/security/identity-signin/manage-user-accounts-in-windows).

## 3. Примени настройку

Файл `AssignedAccess.xml` запускает `C:\QostanaiProctor\QostanaiProctor.exe` для пользователя `ProctorKiosk`. Прежде чем применять профиль, убедись, что обычная администраторская учётная запись и её пароль доступны.

1. Скачай **PsExec** только с [официальной страницы Microsoft Sysinternals](https://learn.microsoft.com/en-us/sysinternals/downloads/psexec) и положи `PsExec64.exe` в эту папку `kiosk`.
2. Открой PowerShell **от имени администратора** и перейди в папку `kiosk` проекта.
3. Запусти следующую команду. Она откроет отдельное окно PowerShell от имени системной учётной записи и применит конфигурацию только к `ProctorKiosk`:

   ```powershell
   .\PsExec64.exe -accepteula -i -s powershell.exe -NoExit -ExecutionPolicy Bypass -File "$PWD\Apply-AssignedAccess.ps1"
   ```

4. Выйди из `ProctorKiosk` и войди в него снова. Киоск-приложение запускается во весь экран.

## Выход и отмена

- Чтобы выйти из киоск-сеанса, нажми **Ctrl+Alt+Del**, выбери выход из учётной записи и войди обратно в свою обычную учётную запись Windows.
- Чтобы удалить профиль киоска, открой административный PowerShell в этой папке и выполни:

  ```powershell
  .\PsExec64.exe -accepteula -i -s powershell.exe -NoExit -ExecutionPolicy Bypass -File "$PWD\Remove-AssignedAccess.ps1"
  ```

Скрипт настройки откажется перезаписывать уже существующий профиль Assigned Access. Конфигурация и запуск здесь подготовлены, но сам киоск включится только после выполнения команд на компьютере.

## Технические заметки

- Для настольного приложения используется `KioskModeApp` с путём `v4:ClassicAppPath`; для Windows 11 эта настройка описана в [схеме Assigned Access от Microsoft](https://learn.microsoft.com/en-us/windows/configuration/assigned-access/configuration-file).
- Применение XML выполняется через Assigned Access CSP. Microsoft указывает запуск WMI Bridge от имени `SYSTEM`; скрипт проверяет это и не запускается из обычного PowerShell.
- Отчёты и снимки упакованного приложения сохраняются в `%LOCALAPPDATA%\QostanaiProctor\reports` отдельного пользователя. Видео не сохраняется.
- Windows может сохранять часть политик multi-app конфигурации после её удаления. Для нашего single-app профиля скрипт отмены очищает Assigned Access XML; для ручного восстановления оставляй основную администраторскую учётную запись вне профиля.
