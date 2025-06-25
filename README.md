# 🧾 Проект ресторана
    Веб-приложение на Django, позволяющее ресторанам и кафе управлять заказами
    В данной версии название кафе "Yummy", вам придется поменять под свой ручным способом. В дальнейшем мы улучшим эту возможность

---
## 📦 Установка
1) Клонируйте этот репозиторий:
    git clone https://github.com/ingarbi/django_restaraunt_system.git
2) Перейдите в папку проекта:
    cd django_restaraunt_system
3) Создайте виртуальное окружение: python -m venv venv
   # На Linux:
    - source venv/bin/activate
   # На Windows:
    - source venv/Scripts/activate
    - cd Scripts
    - activate
5) Установите зависимости:
    pip install -r requirements.txt
6) Примените миграции:
    python manage.py migrate
7) Создайте суперпользователя:
    python manage.py createsuperuser
8) Запустите сервер:
    python manage.py runserver
9) Откройте в браузере:  http://127.0.0.1:8000/




<!--  -->
Here’s the full checklist:

🛠 Step-by-step setup:
Install Python (make sure the same version as your project, for example Python 3.10+)

https://www.python.org/downloads/

Install Git (optional, but good if you send project over Git)

https://git-scm.com/

Copy project folder onto his PC.

Create virtual environment (only once):

Open command line in the project folder and run:

bash
Копировать
Редактировать
python -m venv venv
Install required packages:

Create a requirements.txt first (on your machine):

bash
Копировать
Редактировать
pip freeze > requirements.txt
Then on his PC:

bash
Копировать
Редактировать
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
(this installs Django, channels, weasyprint, etc.)

Migrate database:

bash
Копировать
Редактировать
python manage.py migrate
Collect static files (if needed for production):

bash
Копировать
Редактировать
python manage.py collectstatic
Run the server by double-clicking your start.bat / running start.sh.
