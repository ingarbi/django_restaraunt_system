@echo off
cd /d %~dp0

echo ==========================
echo Activating virtual environment...
echo ==========================
call venv\Scripts\activate

echo ==========================
echo Updating project...
echo ==========================
git pull origin main

echo ==========================
echo Installing dependencies...
echo ==========================
pip install -r req.txt

echo ==========================
echo Running migrations...
echo ==========================
python manage.py makemigrations
python manage.py migrate

echo ==========================
echo Done! Project updated.
echo This window will close automatically in 10 seconds...
echo ==========================
timeout /t 10 /nobreak >nul
exit
