#!/usr/bin/env python3
"""
SLSU - Judge Guillermo Eleazar | Facility & Equipment Request System
✅ ALL-IN-ONE FILE: Code + Templates included
✅ Supabase PostgreSQL Ready
✅ Fixed: No more login.html not found error
✅ Fixed: Auto-increment ID for users
"""

import os
import sys
from datetime import datetime, date, timedelta
from flask import (Flask, g, request, session, redirect, url_for,
                   render_template_string, flash)
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------- CONFIGURATION --------------------------
BASE = os.path.dirname(os.path.abspath(__file__))

DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
USE_PG = bool(DATABASE_URL)

if USE_PG:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("❌ psycopg2 not installed! Run: pip install psycopg2-binary")
        sys.exit(1)
else:
    import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "change-this-secret-key-in-production"
app.permanent_session_lifetime = timedelta(hours=8)

FACILITIES = ["Audio Visual Room (AVR)", "Administration Building Lobby", "Covered Court", "Classroom"]
EQUIPMENT_DEFAULTS = [("Sound System", 2), ("Table", 30), ("Chair", 200), ("Microphone", 6), ("Projector", 3)]

# -------------------------- ALL HTML TEMPLATES (Embedded) --------------------------
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="tl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SLSU — Facility & Equipment Request</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, msg in messages %}
              <div class="alert alert-{{ 'danger' if category == 'danger' else 'success' if category == 'success' else 'warning' }} alert-dismissible fade show" role="alert">
                {{ msg }}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
              </div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

LOGIN_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """
<div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card shadow">
            <div class="card-body p-4">
                <h3 class="text-center mb-4">🔐 Mag-Log In</h3>
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="form-control" required autofocus>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button class="btn btn-primary w-100">Mag-Log In</button>
                </form>
                <p class="text-center mt-3">
                    Wala pang account? <a href="{{ url_for('signup') }}">Mag-signup dito</a>
                </p>
            </div>
        </div>
    </div>
</div>
    """
)

SIGNUP_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """
<div class="row justify-content-center">
    <div class="col-md-5">
        <div class="card shadow">
            <div class="card-body p-4">
                <h3 class="text-center mb-4">📝 Gumawa ng Account</h3>
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label">Buong Pangalan</label>
                        <input type="text" name="fullname" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Username</label>
                        <input type="text" name="username" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Email</label>
                        <input type="email" name="email" class="form-control">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Password</label>
                        <input type="password" name="password" class="form-control" required>
                        <small class="text-muted">Hindi bababa sa 6 na karakter</small>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Kumpirmahin ang Password</label>
                        <input type="password" name="confirm_password" class="form-control" required>
                    </div>
                    <button class="btn btn-success w-100">Gumawa ng Account</button>
                </form>
                <p class="text-center mt-3">
                    May account na? <a href="{{ url_for('login') }}">Mag-login dito</a>
                </p>
            </div>
        </div>
    </div>
</div>
    """
)

DASHBOARD_TEMPLATE = BASE_TEMPLATE.replace(
    "{% block content %}{% endblock %}",
    """
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card shadow">
            <div class="card-body p-4">
                <h2 class="text-center mb-4">👋 Kamusta, {{ fullname }}!</h2>
                <p class="lead text-center">Ikaw ay nakapasok bilang: <strong>{{ role }}</strong></p>
                <hr>
                <div class="text-center">
                    <a href="{{ url_for('logout') }}" class="btn btn-danger">Mag-Log Out</a>
                </div>
            </div>
        </div>
    </div>
</div>
    """
)

# -------------------------- DATABASE CONNECTION --------------------------
def get_db():
    if USE_PG:
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = psycopg2.connect(DATABASE_URL)
        return db
    else:
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(os.path.join(BASE, "rfu.db"))
            db.row_factory = sqlite3.Row
        return db

@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# -------------------------- DATABASE INITIALIZATION --------------------------
def init_db():
    with app.app_context():
        conn = get_db()
        if USE_PG:
            cur = conn.cursor()

            # ✅ SERIAL = Auto-increment ID — FIXED the NULL ID error
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'requester',
                    fullname TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS equipment (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    available INTEGER NOT NULL DEFAULT 0
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id),
                    fullname TEXT,
                    purpose TEXT,
                    facility TEXT NOT NULL,
                    request_date DATE NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS request_equipment (
                    id SERIAL PRIMARY KEY,
                    request_id INTEGER NOT NULL REFERENCES requests(id),
                    equipment_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1
                )
            """)

            # Default Admin Account
            cur.execute("SELECT id FROM users WHERE username = %s", ("admin",))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO users (username, password, role, fullname)
                    VALUES (%s, %s, %s, %s)
                """, ("admin", generate_password_hash("admin123", method='pbkdf2:sha256'), "admin", "System Administrator"))

            # Default Equipment
            cur.execute("SELECT COUNT(*) FROM equipment")
            if cur.fetchone()[0] == 0:
                for name, qty in EQUIPMENT_DEFAULTS:
                    cur.execute("""
                        INSERT INTO equipment (name, quantity, available)
                        VALUES (%s, %s, %s)
                    """, (name, qty, qty))

            conn.commit()
            cur.close()
            print("✅ Supabase PostgreSQL Ready!")

        else:
            # SQLite — Local Fallback
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'requester',
                    fullname TEXT,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    available INTEGER NOT NULL DEFAULT 0
                )
            """)
            cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO users (username, password, role, fullname)
                    VALUES (?, ?, ?, ?)
                """, ("admin", generate_password_hash("admin123", method='pbkdf2:sha256'), "admin", "System Administrator"))
            cursor.execute("SELECT COUNT(*) FROM equipment")
            if cursor.fetchone()[0] == 0:
                for name, qty in EQUIPMENT_DEFAULTS:
                    cursor.execute("""
                        INSERT INTO equipment (name, quantity, available)
                        VALUES (?, ?, ?)
                    """, (name, qty, qty))
            conn.commit()
            print("✅ SQLite Local DB Ready!")

# -------------------------- ROUTES --------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'gso':
            return redirect(url_for('gso_dashboard'))
        else:
            return redirect(url_for('requester_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash('Ilagay ang username at password!', 'danger')
            return render_template_string(LOGIN_TEMPLATE)

        try:
            conn = get_db()
            if USE_PG:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute("SELECT * FROM users WHERE username = %s", (username,))
                user = cur.fetchone()
                cur.close()
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                user = cursor.fetchone()

            if user and check_password_hash(user['password'], password):
                session.clear()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['fullname'] = user['fullname'] or user['username']
                session.permanent = True
                flash(f'✅ Maligayang pagbabalik, {session["fullname"]}!', 'success')
                return redirect(url_for('index'))
            else:
                flash('❌ Maling username o password!', 'danger')
        except Exception as e:
            flash(f'❌ Error: {str(e)}', 'danger')
            print(f"Login Error: {e}")

    return render_template_string(LOGIN_TEMPLATE)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        fullname = request.form.get('fullname', '').strip()
        email = request.form.get('email', '').strip()

        if not all([username, password, confirm_password, fullname]):
            flash('Punan ang lahat ng kinakailangang patlang!', 'danger')
            return render_template_string(SIGNUP_TEMPLATE)

        if password != confirm_password:
            flash('❌ Hindi magkatugma ang password!', 'danger')
            return render_template_string(SIGNUP_TEMPLATE)

        if len(password) < 6:
            flash('❌ Ang password ay hindi bababa sa 6 na karakter!', 'danger')
            return render_template_string(SIGNUP_TEMPLATE)

        try:
            conn = get_db()
            if USE_PG:
                cur = conn.cursor()
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    flash('❌ Ang username ay ginagamit na!', 'warning')
                    return render_template_string(SIGNUP_TEMPLATE)

                # ✅ HINDI kasama ang 'id' — SERIAL ang bahala
                cur.execute("""
                    INSERT INTO users (username, password, role, fullname, email)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    username,
                    generate_password_hash(password, method='pbkdf2:sha256'),
                    'requester',
                    fullname,
                    email
                ))
                conn.commit()
                cur.close()
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    flash('❌ Ang username ay ginagamit na!', 'warning')
                    return render_template_string(SIGNUP_TEMPLATE)
                cursor.execute("""
                    INSERT INTO users (username, password, role, fullname, email)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    username,
                    generate_password_hash(password, method='pbkdf2:sha256'),
                    'requester',
                    fullname,
                    email
                ))
                conn.commit()

            flash('✅ Matagumpay ang paggawa ng account! Mag-login na.', 'success')
            return redirect(url_for('login'))

        except Exception as e:
            flash(f'❌ Error: {str(e)}', 'danger')
            print(f"Signup Error: {e}")

    return render_template_string(SIGNUP_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    flash('✅ Nakalabas na sa system.', 'info')
    return redirect(url_for('login'))

@app.route('/requester/dashboard')
def requester_dashboard():
    if 'user_id' not in session or session.get('role') != 'requester':
        return redirect(url_for('login'))
    return render_template_string(DASHBOARD_TEMPLATE, fullname=session['fullname'], role='Requester')

@app.route('/gso/dashboard')
def gso_dashboard():
    if 'user_id' not in session or session.get('role') != 'gso':
        return redirect(url_for('login'))
    return render_template_string(DASHBOARD_TEMPLATE, fullname=session['fullname'], role='GSO Officer')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return render_template_string(DASHBOARD_TEMPLATE, fullname=session['fullname'], role='Administrator')

# -------------------------- RUN --------------------------
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
