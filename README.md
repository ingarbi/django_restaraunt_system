# ***A&I Resto*** - программа для автоматизации процессов вашего заведения

## Пошаговое руководство для установки программы

> ### Часть первая. Установка необходимых библиотек


1) Скачать и установить Python 3.12.2 по
    [ссылке](https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe)

2) Скачать и установить Git по
    [ссылке](https://github.com/git-for-windows/git/releases/download/v2.50.0.windows.1/Git-2.50.0-64-bit.exe)

3) Клонировать этот репозиторий
    `git clone https://github.com/ingarbi/django_restaraunt_system.git` 

4) Установить уже из заклонированного репо GTK (файл с названием gtk3-win64.exe)

5) В папке где клон репо на компьютере нужно открыть командную строку и выполнить следующие команды:
     > 1. `python -m venv venv`
     > 2. `.\venv\Scripts\Activate.ps1` или `.\venv\Scripts\activate.bat`
     > 3. `pip install -r req.txt` 
     > 4. `python manage.py makemigrations` 
     > 5. `python manage.py migrate` 
     > 6. `python manage.py createsuperuser` 
     > 7. `python manage.py runserver 0.0.0.0:8000` 

6) Открыть ссылку http://127.0.0.1:8000/ в любом браузере, перейти в админку и создать профиль для текущего аккаунта.

>### Часть вторая. Установка браузера Mozilla Firefox

1) Скачать и установить Mozilla Firefox версия 77.0.1, по  [ссылке](https://ftp.mozilla.org/pub/firefox/releases/77.0/win64/ru/Firefox%20Setup%2077.0.exe)

2) После установки нужно выполнить следующие действия для печати без вспомогательного окна:

    1) Настроить Firefox в настройках:
        
            Нажмите кнопку меню «Меню» в правом верхнем углу, затем выберите «Параметры».
            На левой панели выберите «Основные».
            Прокрутите вниз до раздела «Обновления Firefox».
            [x] и выбрать "Никогда не проверять наличие обновлений".
     
    2) Дальше нужно в адресной строке браузера поставить в значении False и True:<br>

            about:config #False
            app.update.auto #False
            app.update.enabled #False
            app.update.service.e­nabled #False
            app.update.silent #False
            print.always_print_silent #True
            
        > В этой части также нужно добавть размер чека в см, при открытии всегда сервер и установить как приложение......(будет сделано позже)

    3) Сверните браузер, затем

            Нажмите Win + R, введите regedit.exe и нажмите Enter.
            Перейдите в HKEY_LOCAL_MACHINE -> SOFTWARE -> Policies
            Кликните правой кнопкой мыши по "Policies" и создайте новый раздел с именем "Mozilla".
            Выделите созданный раздел "Mozilla" и внутри него создайте подраздел "Firefox". Затем выберите "Firefox".

            В разделе HKEY_LOCAL_MACHINE -> SOFTWARE -> Policies -> Mozilla -> Firefox кликните правой кнопкой мыши по правой части окна и выберите "Создать" -> "Параметр DWORD (32 бита)". 
            Назовите параметр "DisableAppUpdate" и установите значение 1.
    

> ### Часть третья. Ярлыки и название

1) Название вашего заведения.

        1) Чтобы поменять стандартное название, открой текстовый файл /main/cafe_name.txt и поменяйте на соответсвующий.

2) Файлы start.bat и update.bat отвечают за запуск и обновление сервера соответсвенно. Отправьте в качестве ярлыков их на рабочий стол

###### P.S.
    python generate_license.py --client cafe123 --days 1