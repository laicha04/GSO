#!/usr/bin/env python3
"""
SLSU - Judge Guillermo Eleazar | Facility & Equipment Request System
FIXED VERSION: Supabase PostgreSQL + ID auto-increment fixed
"""
import os, io, re, sys, json, time, base64, secrets, sqlite3
from calendar import Calendar
from datetime import datetime, date, timedelta, timezone
from flask import (Flask, g, request, session, redirect, url_for, render_template,
                   flash, abort, send_file, jsonify, Response)
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
USE_PG = bool(DATABASE_URL)

if USE_PG:
    import psycopg2, psycopg2.extras

DB_PATH = os.environ.get("RFU_DB", os.path.join(BASE, "rfu.db"))
FACILITIES = ["Audio Visual Room (AVR)", "Administration Building Lobby", "Covered Court", "Classroom"]
OLD_DEFAULTS = [("Sound System", 2), ("Table", 30), ("Chair", 200), ("Microphone", 6), ("Projector", 3)]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "change-this-secret-key-in-production"
app.permanent_session_lifetime = timedelta(hours=8)

# -------------------------- DATABASE CONNECTION --------------------------
def get_db():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    else:
        db = getattr(g, '_database', None)
        if db is None:
            db = g._database = sqlite3.connect(DB_PATH)
            db.row_factory = sqlite3.Row
        return db

@app.teardown_appcontext
def close_db(exception):
    if USE_PG:
        pass
    else:
        db = getattr(g, '_database', None)
        if db is not None:
            db.close()

# -------------------------- FIXED DATABASE INIT --------------------------
def init_db():
    with app.app_context():
        conn = get_db()
        if USE_PG:
            cur = conn.cursor()
            
            # ✅ AYUSIN: DROP at RECREATE gamit ang SERIAL para sa auto-id
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

            # ✅ Default Admin — HINDI isinama ang id
            cur.execute("SELECT id FROM users WHERE username = %s", ("admin",))
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO users (username, password, role, fullname)
                    VALUES (%s, %s, %s, %s)
                """, ("admin", generate_password_hash("admin123", method='pbkdf2:sha256'), "admin", "System Administrator"))

            # ✅ Default Equipment
            cur.execute("SELECT COUNT(*) FROM equipment")
            if cur.fetchone()[0] == 0:
                for name, qty in OLD_DEFAULTS:
                    cur.execute("""
                        INSERT INTO equipment (name, quantity, available)
                        VALUES (%s, %s, %s)
                    """, (name, qty, qty))

            conn.commit()
            cur.close()
            print("✅ Supabase DB Initialized — SERIAL IDs enabled!")

        else:
            # SQLite version — walang binago
            db = conn
            cursor = db.cursor()
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS request_equipment (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id INTEGER NOT NULL REFERENCES requests(id),
                    equipment_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1
                )
            """)
            cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO users (username, password, role, fullname)
                    VALUES (?, ?, ?, ?)
                """, ("admin", generate_password_hash("admin123", method='pbkdf2:sha256'), "admin", "System Administrator"))
            cursor.execute("SELECT COUNT(*) as count FROM equipment")
            if cursor.fetchone()['count'] == 0:
                for name, qty in OLD_DEFAULTS:
                    cursor.execute("""
                        INSERT INTO equipment (name, quantity, available)
                        VALUES (?, ?, ?)
                    """, (name, qty, qty))
            db.commit()
            print("✅ SQLite DB Initialized!")

# -------------------------- FIXED SIGNUP ROUTE --------------------------
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

        # Validation
        if not all([username, password, confirm_password, fullname]):
            flash('Punan ang lahat ng kinakailangang patlang!', 'danger')
            return render_template('signup.html')
        if password != confirm_password:
            flash('❌ Hindi magkatugma ang password!', 'danger')
            return render_template('signup.html')
        if len(password) < 6:
            flash('❌ Ang password ay hindi bababa sa 6 na karakter!', 'danger')
            return render_template('signup.html')

        try:
            conn = get_db()
            if USE_PG:
                cur = conn.cursor()
                # Check duplicate
                cur.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cur.fetchone():
                    flash('❌ Ang username ay ginagamit na!', 'warning')
                    return render_template('signup.html')
                
                # ✅ AYUSIN: HINDI isinama ang id — SERIAL ang bahala
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
                # SQLite version
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    flash('❌ Ang username ay ginagamit na!', 'warning')
                    return render_template('signup.html')
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

    return render_template('signup.html')

# -------------------------- KOPYAHIN ANG IBA PANG ROUTES MO DITO --------------------------
# Iwan ang lahat ng iba pang code — login, logout, dashboards — walang binago

@app.route('/')
def index():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif session.get('role') == 'gso':
            return redirect(url_for('gso_dashboard'))
        else:
            return redirect(url_for('requester_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Ilagay ang username at password!', 'danger')
            return render_template('login.html')
        try:
            conn = get_db()
            if USE_PG:
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
            flash('❌ Maling username o password!', 'danger')
        except Exception as e:
            flash(f'❌ Error: {str(e)}', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('✅ Nakalabas na sa system.', 'info')
    return redirect(url_for('login'))

# Dashboards — panatilihin ang orihinal mo
@app.route('/requester/dashboard')
def requester_dashboard():
    if 'user_id' not in session or session.get('role') != 'requester':
        return redirect(url_for('login'))
    return f"<h1>Requester Dashboard</h1><p>Welcome, {session['fullname']}!</p><a href='/logout'>Logout</a>"

@app.route('/gso/dashboard')
def gso_dashboard():
    if 'user_id' not in session or session.get('role') != 'gso':
        return redirect(url_for('login'))
    return f"<h1>GSO Dashboard</h1><p>Welcome, {session['fullname']}!</p><a href='/logout'>Logout</a>"

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    return f"<h1>Admin Dashboard</h1><p>Welcome, {session['fullname']}!</p><a href='/logout'>Logout</a>"

# -------------------------- RUN --------------------------
with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
