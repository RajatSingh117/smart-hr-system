# Smart HR & Employee Management System

## Setup (Windows)
```
git clone https://github.com/RajatSingh117/smart-hr-system.git
cd smart-hr-system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py runserver
```

## Team rules
1. Never push to `main`. Work on `feature/<app>-<task>` branches and open a Pull Request.
2. Edit only your own app folder. Do not edit `config/settings.py`, `config/urls.py`, `templates/base.html` or `requirements.txt` without telling the leader.
3. Run `git pull --rebase origin main` every morning.
4. Do not commit `.env`, `venv/` or `db.sqlite3`.

## Branch workflow
```
git checkout -b feature/employees-crud
git add .
git commit -m "employees: add create form"
git push -u origin feature/employees-crud
```
Then open a Pull Request on GitHub.