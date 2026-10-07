# Ограничение рабочего окружения Windows

Во время демо-теста приложение временно блокирует основные сочетания клавиш через Python-библиотеку `keyboard`. Блокировка снимается при закрытии теста. Заблокированные нажатия и потеря фокуса записываются в журнал.

## Что блокируется в демо-тесте

- Alt+Tab, Alt+Shift+Tab и другие сочетания переключения окон;
- клавиша Windows;
- Ctrl+C/Ctrl+V и варианты копирования/вставки через Insert;
- Ctrl+Tab и Ctrl+Shift+Tab для переключения вкладок;
- Print Screen;
- основные сочетания закрытия окна и запуска системных меню.

## Ограничения Windows

Это локальная блокировка клавиатуры, пока открыто окно теста. Она не блокирует Ctrl+Alt+Del. Переключение через мышь или другие системные средства может сработать; приложение запишет потерю фокуса и возврат. Прототип не запрещает запуск стороннего браузера на уровне Windows и не заменяет защищённый экзаменационный браузер.

Для дополнительного ограничения приложений Windows 11 Pro поддерживает Assigned Access в виде ограниченного профиля, однако Microsoft указывает, что Alt+Tab и Alt+Shift+Tab там остаются доступны. Microsoft Keyboard Filter поддерживается Windows Enterprise, Education и IoT Enterprise; он не входит в обычную редакцию Pro. Однооконный киоск Assigned Access предназначен для UWP-приложений и Edge, а не для нашего настольного Python-приложения. Подробнее: [Assigned Access](https://learn.microsoft.com/en-us/windows/configuration/assigned-access/recommendations), [варианты киоска](https://learn.microsoft.com/en-us/windows/configuration/kiosk/), [Keyboard Filter](https://learn.microsoft.com/en-us/windows/configuration/keyboard-filter/).

Файлы `AssignedAccess.xml`, `Apply-AssignedAccess.ps1` и `Remove-AssignedAccess.ps1` — старый черновик, не запускай их для этой версии прототипа.
