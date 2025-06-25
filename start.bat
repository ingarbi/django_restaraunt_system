@echo off
cd cafe_system 
call venv\Scripts\activate
python manage.py runserver
pause
