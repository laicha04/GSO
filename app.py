#!/usr/bin/env python3
"""
SLSU - Judge Guillermo Eleazar | Facility & Equipment Request System
PostgreSQL/Supabase version — DATA PERMANENT, HINDI NA MAWAWALA!

SETUP:
  Environment Variables:
    DATABASE_URL = postgresql://... (Neon/Supabase connection string)
    SECRET_KEY = iyong-susi-dito

FIRST LOGIN:
  Username: admin | Password: admin123
"""

import os
import sys
from datetime import datetime, date, timedelta
from flask import (Flask, g, request, session, redirect, url_for,
                   render_template, flash, send_file, jsonify)
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# -------------------------- CONFIGURATION --------------------------
BASE = os.path.dirname(os.path.abspath(__file__))

# Database Connection
DATABASE_URL = (os.environ.get("DATABASE_URL") or "").strip()
if not DATABASE_URL:
    print("⚠️  DATABASE_URL not set!")
    sys.exit(1)

USE_PG = True
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "change-this-strong-secret-key-in-production"
app.permanent_session_lifetime = timedelta(hours=8)

FACILITIES = ["Audio Visual Room (AVR)", "Administration Building Lobby", "Covered Court", "Classroom"]

# -------------------------- DATABASE CONNECTION --------------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = psycopg2.connect(DATABASE_URL)
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
        cur = conn.cursor()

        # Users Table
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

        # Equipment Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS equipment (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                available INTEGER NOT NULL DEFAULT 0
            )
        """)

        # Requests Table
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

        # Requested Equipment Table
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
            defaults = [
                ("Sound System", 2),
                ("Table", 30),
                ("Chair", 200),
                ("Microphone", 6),
                ("Projector", 3)
            ]
            for name, qty in defaults:
                cur.execute("""
                    INSERT INTO equipment (name, quantity, available)
                    VALUES (%s, %s, %s)
                """, (name, qty, qty))

        conn.commit()
        cur.close()
        print("✅ Database initialized successfully!")

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
            return render_template('login.html')

        try:
            conn = get_db()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()

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

    return render_template('login.html')

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
            cur = conn.cursor()

            # Check duplicate username
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                flash('❌ Ang username ay ginagamit na!', 'warning')
                return render_template('signup.html')

            # Insert new user
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

            flash('✅ Matagumpay ang paggawa ng account! Mag-login na.', 'success')
            return redirect(url_for('login'))

        except psycopg2.IntegrityError as e:
            flash(f'❌ Ang username o email ay ginagamit na!', 'danger')
        except Exception as e:
            flash(f'❌ Error sa paggawa ng account: {str(e)}', 'danger')
            print(f"Signup Error: {e}")

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('✅ Nakalabas na sa system.', 'info')
    return redirect(url_for('login'))

# -------------------------- DASHBOARDS --------------------------
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
