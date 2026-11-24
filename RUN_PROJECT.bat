@echo off
echo AI Employee Task Manager
echo.
py -m pip install -r requirements.txt
py manage.py migrate
py manage.py seed_demo
py manage.py runserver
pause
