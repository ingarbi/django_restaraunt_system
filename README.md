# 🧾 Проект ресторана

    Веб-приложение на Django, позволяющее ресторанам и кафе управлять заказами
    В данной версии название кафе "{{CAFE_NAME}}", вам придется поменять под свой d /main/cafe_name.txt.

## Требования

1) Install Python
    Python version is 3.12.2
    url for download [text](https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe)
2) Install Git (optional, but good if you send project over Git)
    [https://www.filepuma.com/download/git_for_windows_64bit_2.46.0-40344/download/](https://github.com/git-for-windows/git/releases/download/v2.50.0.windows.1/Git-2.50.0-64-bit.exe)
    or <https://git-scm.com/>

3) Clone repository:
    [https://github.com/ingarbi/django_restaraunt_system.git](https://github.com/ingarbi/django_restaraunt_system.git)

4) Install GTK from cloned repository

5) Create virtual environment:
    python -m venv venv

6) Activate virtual environment:
    venv\Scripts\activate # Windows

7) Install required packages:
    pip install -r requirements.txt

8) Apply migrations:
    python manage.py makemigrations
    python manage.py migrate

9) Create superuser:
    python manage.py createsuperuser

10) Create usual user in admin panel

11) Run server:
    python manage.py runserver 0.0.0.0:8000

12) Run the server by double-clicking your start.bat / running start.sh.

## 📦 Установка

1) Клонируйте этот репозиторий:
    git clone <https://github.com/ingarbi/django_restaraunt_system.git>
2) Перейдите в папку проекта:
    cd django_restaraunt_system
3) Создайте виртуальное окружение: python -m venv venv

   ### На Linux

    - source venv/bin/activate

   ### На Windows

    - source venv/Scripts/activate
    - cd Scripts
    - activate
4) Установите зависимости:
    pip install -r requirements.txt
5) Примените миграции:
    python manage.py migrate
6) Создайте суперпользователя:
    python manage.py createsuperuser
7) Запустите сервер:
    python manage.py runserver
8) Откройте в браузере:  <http://127.0.0.1:8000/>
