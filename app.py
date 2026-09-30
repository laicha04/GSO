#!/usr/bin/env python3
"""
SLSU - Judge Guillermo Eleazar | Facility & Equipment Request System
Single-file Flask + SQLite application.

SETUP
    pip install flask reportlab
    python app.py                  -> open http://127.0.0.1:5000

FIRST LOGIN
    username: admin    password: admin123   (you MUST change it on first login)
    Forgot the admin password?  ->  python app.py reset-admin

OPTIONAL ENVIRONMENT VARIABLES
    RFU_DB=/path/rfu.db  RFU_ADMIN_PASSWORD=...  HOST=0.0.0.0  PORT=8000
For real deployment use HTTPS and a WSGI server, e.g.:  pip install waitress ; waitress-serve --port=8000 app:app
"""
import os, io, re, sys, json, time, base64, secrets, sqlite3
from calendar import Calendar
from datetime import datetime, date
from flask import (Flask, g, request, session, redirect, url_for, render_template,
                   flash, abort, send_file, jsonify, Response)
from jinja2 import DictLoader
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("RFU_DB", os.path.join(BASE, "rfu.db"))
FACILITIES = ["Audio Visual Room (AVR)", "Administration Building Lobby", "Covered Court", "Classroom"]
DEFAULT_STOCK = [("Sound System", 2), ("Table", 30), ("Chair", 200), ("Microphone", 6), ("Projector", 3)]
LOGOS = {"1": "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",   # SLSU seal (left)
         "2": "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"}   # Judge Guillermo Eleazar seal (right)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    _kf = os.path.join(BASE, "rfu_secret.key")
    if not os.path.exists(_kf):
        open(_kf, "w").write(secrets.token_hex(32))
    app.secret_key = open(_kf).read().strip()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

# ------------------------------------------------------------------ database
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, fullname TEXT NOT NULL,
  student_no TEXT NOT NULL, pw_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'student', must_change INTEGER DEFAULT 0,
  created_at TEXT);
CREATE TABLE IF NOT EXISTS inventory(name TEXT PRIMARY KEY COLLATE NOCASE, stock INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY, rfu_no TEXT, user_id INTEGER NOT NULL, requester TEXT, dept TEXT,
  event TEXT, event_date TEXT, t1 TEXT, t2 TEXT, attendees TEXT, facilities TEXT DEFAULT '[]', head TEXT,
  status TEXT DEFAULT 'Pending', remarks TEXT DEFAULT '', created_at TEXT, returned_at TEXT);
CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, request_id INTEGER NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
  name TEXT NOT NULL, qty INTEGER NOT NULL);
"""

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def _close(_):
    d = g.pop("db", None)
    if d: d.close()

def q(sql, *a): return db().execute(sql, a).fetchall()
def q1(sql, *a): return db().execute(sql, a).fetchone()
def ex(sql, *a):
    c = db().execute(sql, a); db().commit(); return c

def now_s(): return datetime.now().strftime("%Y-%m-%d %H:%M")

def init_db():
    with app.app_context():
        db().executescript(SCHEMA)
        if not q1("SELECT 1 FROM inventory"):
            for n, s in DEFAULT_STOCK: ex("INSERT INTO inventory VALUES(?,?)", n, s)
        if not q1("SELECT 1 FROM users WHERE username='admin'"):
            ex("INSERT INTO users(username,fullname,student_no,pw_hash,role,must_change,created_at) VALUES('admin','GSO Administrator','-',?, 'admin',1,?)",
               generate_password_hash(os.environ.get("RFU_ADMIN_PASSWORD", "admin123")), now_s())

# ------------------------------------------------------------------ security helpers
FAILS = {}
def is_locked(key):
    c = FAILS.get(key)
    return bool(c and c[0] >= 5 and time.time() - c[1] < 300)
def fail(key):
    c = FAILS.get(key, (0, 0)); FAILS[key] = (c[0] + 1, time.time())

def csrf():
    if "_csrf" not in session: session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]

@app.before_request
def _guard():
    if request.method == "POST" and not secrets.compare_digest(request.form.get("_csrf", ""), session.get("_csrf", "-")):
        abort(400, "Invalid form token. Please go back, refresh the page and try again.")
    g.user = q1("SELECT * FROM users WHERE id=?", session["uid"]) if "uid" in session else None
    if g.user and g.user["must_change"] and request.endpoint not in ("account", "logout", "logo", "static", None):
        flash("Please change your password before continuing.", "err")
        return redirect(url_for("account"))

def login_required(f):
    from functools import wraps
    @wraps(f)
    def w(*a, **k):
        if not g.user: return redirect(url_for("login"))
        return f(*a, **k)
    return w

def admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def w(*a, **k):
        if g.user["role"] != "admin": abort(403)
        return f(*a, **k)
    return w

def valid_pw(p, p2):
    if len(p) < 8: return "Password must be at least 8 characters."
    if p != p2: return "Passwords do not match."
    return None

# ------------------------------------------------------------------ availability logic
def committed(name, d, t1, t2, exclude=0):
    """Units of `name` unavailable for the slot: (a) pending/approved requests overlapping the slot,
    (b) approved requests whose event already ended but were NOT marked Returned yet."""
    r = q1("""SELECT COALESCE(SUM(i.qty),0) s FROM items i JOIN requests r ON r.id=i.request_id
              WHERE i.name=? COLLATE NOCASE AND r.id!=? AND r.returned_at IS NULL AND (
                (r.status IN ('Pending','Approved') AND r.event_date=? AND r.t1<? AND ?<r.t2)
                OR (r.status='Approved' AND (r.event_date||' '||r.t2)<=?))""",
           name, exclude, d, t2, t1, now_s())
    return r["s"]

def stock_of(name):
    r = q1("SELECT name,stock FROM inventory WHERE name=?", name)
    return (r["name"], r["stock"]) if r else (None, None)

def left(name, d, t1, t2, exclude=0):
    n, s = stock_of(name)
    return None if n is None else max(0, s - committed(n, d, t1, t2, exclude))

def booked_facilities(d, t1, t2, exclude=0):
    s = set()
    for r in q("SELECT facilities FROM requests WHERE event_date=? AND status IN ('Pending','Approved') AND t1<? AND ?<t2 AND id!=?",
               d, t2, t1, exclude):
        s.update(x.lower() for x in json.loads(r["facilities"]))
    return s

def parse_slot(d, t1, t2):
    try:
        datetime.strptime(d, "%Y-%m-%d"); a = datetime.strptime(t1, "%H:%M"); b = datetime.strptime(t2, "%H:%M")
        return b > a
    except Exception:
        return False

@app.route("/api/availability")
@login_required
def api_availability():
    d, t1, t2 = (request.args.get(k, "") for k in ("d", "t1", "t2"))
    ok = parse_slot(d, t1, t2)
    out = {"booked": sorted(booked_facilities(d, t1, t2)) if ok else [], "left": {}}
    for r in q("SELECT name,stock FROM inventory"):
        out["left"][r["name"]] = left(r["name"], d, t1, t2) if ok else r["stock"]
    return jsonify(out)

# ------------------------------------------------------------------ auth routes
@app.route("/logo/<n>.jpg")
def logo(n):
    if n not in LOGOS: abort(404)
    return Response(base64.b64decode(LOGOS[n]), mimetype="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username", "").strip().lower()
        key = u + "|" + (request.remote_addr or "")
        if is_locked(key):
            flash("Too many failed attempts. Please wait 5 minutes.", "err")
        else:
            r = q1("SELECT * FROM users WHERE username=?", u)
            if r and check_password_hash(r["pw_hash"], request.form.get("password", "")):
                FAILS.pop(key, None); session.clear(); session["uid"] = r["id"]; csrf()
                return redirect(url_for("dashboard"))
            fail(key); flash("Incorrect username or password.", "err")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        f = request.form
        fn, sn, u = f.get("fullname", "").strip(), f.get("student_no", "").strip(), f.get("username", "").strip().lower()
        err = None
        if not (fn and sn and u and f.get("password")): err = "Please fill in all fields."
        elif not re.fullmatch(r"[a-z0-9_.]{3,30}", u): err = "Username: 3-30 letters, numbers, . or _"
        elif valid_pw(f.get("password", ""), f.get("confirm", "")): err = valid_pw(f["password"], f["confirm"])
        elif q1("SELECT 1 FROM users WHERE username=?", u): err = "That username is already taken."
        if err: flash(err, "err")
        else:
            ex("INSERT INTO users(username,fullname,student_no,pw_hash,role,created_at) VALUES(?,?,?,?, 'student',?)",
               u, fn, sn, generate_password_hash(f["password"]), now_s())
            flash("Account created! You can now sign in.", "ok"); return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        f = request.form; u = f.get("username", "").strip().lower(); key = "fp|" + (request.remote_addr or "")
        r = q1("SELECT * FROM users WHERE username=?", u)
        if is_locked(key): flash("Too many failed attempts. Please wait 5 minutes.", "err")
        elif r and r["role"] == "admin":
            flash("Admin passwords cannot be reset here. Run 'python app.py reset-admin' on the server.", "err")
        elif not (r and r["student_no"].strip() == f.get("student_no", "").strip()
                  and r["fullname"].strip().lower() == f.get("fullname", "").strip().lower()):
            fail(key); flash("The details you entered do not match our records.", "err")
        elif valid_pw(f.get("password", ""), f.get("confirm", "")): flash(valid_pw(f["password"], f["confirm"]), "err")
        else:
            FAILS.pop(key, None)
            ex("UPDATE users SET pw_hash=?, must_change=0 WHERE id=?", generate_password_hash(f["password"]), r["id"])
            flash("Your password has been changed. Please sign in.", "ok"); return redirect(url_for("login"))
    return render_template("forgot.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        f = request.form
        if not check_password_hash(g.user["pw_hash"], f.get("current", "")): flash("Current password is incorrect.", "err")
        elif valid_pw(f.get("password", ""), f.get("confirm", "")): flash(valid_pw(f["password"], f["confirm"]), "err")
        elif f["password"] == f["current"]: flash("New password must be different from the current one.", "err")
        else:
            ex("UPDATE users SET pw_hash=?, must_change=0 WHERE id=?", generate_password_hash(f["password"]), g.user["id"])
            flash("Password updated.", "ok"); return redirect(url_for("dashboard"))
    return render_template("account.html")

# ------------------------------------------------------------------ dashboards
def enrich(rows):
    out = []
    for r in rows:
        d = dict(r); d["fac"] = json.loads(r["facilities"] or "[]")
        d["its"] = [dict(i) for i in q("SELECT name,qty FROM items WHERE request_id=?", r["id"])]
        d["res"] = ", ".join(d["fac"] + ["%s x%d" % (i["name"], i["qty"]) for i in d["its"]]) or "-"
        d["badge"] = "Returned" if r["returned_at"] else r["status"]
        out.append(d)
    return out

def calendar_ctx():
    m = request.args.get("m") or date.today().strftime("%Y-%m")
    try: y, mo = int(m[:4]), int(m[5:7]); date(y, mo, 1)
    except Exception: y, mo = date.today().year, date.today().month
    ym = "%04d-%02d" % (y, mo)
    days = {}
    for r in enrich(q("SELECT * FROM requests WHERE status IN ('Pending','Approved') AND substr(event_date,1,7)=? ORDER BY t1", ym)):
        days.setdefault(int(r["event_date"][8:10]), []).append(r)
    py, pm = (y - 1, 12) if mo == 1 else (y, mo - 1); ny, nm = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return dict(weeks=Calendar(6).monthdayscalendar(y, mo), days=days, title=date(y, mo, 1).strftime("%B %Y"),
                prev="%04d-%02d" % (py, pm), next="%04d-%02d" % (ny, nm))

@app.route("/")
@login_required
def home(): return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    tab = request.args.get("tab", "")
    if g.user["role"] == "admin":
        tab = tab if tab in ("pending", "approved", "returned", "disapproved", "cal", "stock", "users") else "pending"
        cnt = {k: q1(s)[0] for k, s in {
            "pending": "SELECT COUNT(*) FROM requests WHERE status='Pending'",
            "approved": "SELECT COUNT(*) FROM requests WHERE status='Approved' AND returned_at IS NULL",
            "returned": "SELECT COUNT(*) FROM requests WHERE status='Approved' AND returned_at IS NOT NULL",
            "disapproved": "SELECT COUNT(*) FROM requests WHERE status='Disapproved'"}.items()}
        ctx = dict(tab=tab, cnt=cnt)
        where = {"pending": "status='Pending'", "approved": "status='Approved' AND returned_at IS NULL",
                 "returned": "status='Approved' AND returned_at IS NOT NULL", "disapproved": "status='Disapproved'"}
        if tab in where: ctx["rows"] = enrich(q("SELECT * FROM requests WHERE %s ORDER BY id DESC" % where[tab]))
        elif tab == "cal": ctx.update(calendar_ctx())
        elif tab == "stock":
            ctx["inv"] = [dict(r, out=q1("""SELECT COALESCE(SUM(i.qty),0) FROM items i JOIN requests r ON r.id=i.request_id
                 WHERE i.name=? COLLATE NOCASE AND r.status='Approved' AND r.returned_at IS NULL AND (r.event_date||' '||r.t1)<=?""",
                 r["name"], now_s())[0]) for r in q("SELECT * FROM inventory ORDER BY name")]
        elif tab == "users": ctx["users"] = q("SELECT * FROM users ORDER BY role, fullname")
        return render_template("admin.html", **ctx)
    tab = tab if tab in ("new", "mine", "cal") else "new"
    ctx = dict(tab=tab, today=date.today().isoformat(), facilities=FACILITIES,
               inv=[r["name"] for r in q("SELECT name FROM inventory ORDER BY name")])
    ctx["mine"] = enrich(q("SELECT * FROM requests WHERE user_id=? ORDER BY id DESC", g.user["id"]))
    if tab == "cal": ctx.update(calendar_ctx())
    return render_template("student.html", **ctx)

# ------------------------------------------------------------------ student: new request
@app.route("/request", methods=["POST"])
@login_required
def new_request():
    f = request.form; g_ = lambda k: f.get(k, "").strip()
    back = redirect(url_for("dashboard", tab="new"))
    if not all(g_(k) for k in ("requester", "dept", "event", "event_date", "t1", "t2")):
        flash("Please fill in all required fields (*).", "err"); return back
    d, t1, t2 = g_("event_date"), g_("t1"), g_("t2")
    if not parse_slot(d, t1, t2): flash("Invalid date/time. End time must be later than start time.", "err"); return back
    if d < date.today().isoformat(): flash("The event date cannot be in the past.", "err"); return back
    att = g_("attendees")
    if att and not att.isdigit(): flash("Attendees must be a number.", "err"); return back
    fac = [x for x in f.getlist("fac") if x in FACILITIES]
    if g_("fac_other"): fac.append(g_("fac_other")[:80])
    busy = booked_facilities(d, t1, t2)
    for x in fac:
        if x.lower() in busy: flash('"%s" is already booked at that time. Check the Calendar tab.' % x, "err"); return back
    tot = {}
    for n, o, qy in zip(f.getlist("item_name"), f.getlist("item_other"), f.getlist("item_qty")):
        n = (o.strip() if n == "__other" else n.strip())[:80]
        try: qy = int(qy)
        except ValueError: qy = 0
        if n and qy > 0:
            canon, _ = stock_of(n); n = canon or n; tot[n] = tot.get(n, 0) + qy
    if not fac and not tot: flash("Please choose a facility or equipment.", "err"); return back
    for n, qy in tot.items():
        l = left(n, d, t1, t2)
        if l is None: continue                      # free-text "Other" equipment: not tracked in stock
        if l <= 0: flash("%s is out of stock for that date and time (borrowed or reserved, not yet returned)." % n, "err"); return back
        if qy > l: flash("Only %d %s available for that date and time." % (l, n), "err"); return back
    c = ex("""INSERT INTO requests(user_id,requester,dept,event,event_date,t1,t2,attendees,facilities,head,created_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?)""", g.user["id"], g_("requester")[:120], g_("dept")[:120], g_("event")[:160], d, t1, t2,
           att, json.dumps(fac), g_("head")[:120], now_s())
    rid = c.lastrowid
    ex("UPDATE requests SET rfu_no=? WHERE id=?", "%d-%04d" % (date.today().year, rid), rid)
    for n, qy in tot.items(): ex("INSERT INTO items(request_id,name,qty) VALUES(?,?,?)", rid, n, qy)
    flash("Request submitted! It is now pending admin approval.", "ok")
    return redirect(url_for("dashboard", tab="mine"))

# ------------------------------------------------------------------ admin actions
@app.route("/admin/request/<int:rid>/<action>", methods=["POST"])
@admin_required
def admin_action(rid, action):
    r = q1("SELECT * FROM requests WHERE id=?", rid)
    if not r: abort(404)
    if action == "approve":
        for i in q("SELECT name,qty FROM items WHERE request_id=?", rid):
            l = left(i["name"], r["event_date"], r["t1"], r["t2"], exclude=rid)
            if l is not None and i["qty"] > l:
                flash("Cannot approve: only %d %s available for that time." % (l, i["name"]), "err")
                return redirect(url_for("dashboard", tab="pending"))
        ex("UPDATE requests SET status='Approved', remarks='', returned_at=NULL WHERE id=?", rid); flash("Request approved.", "ok")
    elif action == "disapprove":
        why = request.form.get("remarks", "").strip()
        if not why: flash("Please enter a reason (remarks) for disapproval.", "err"); return redirect(request.referrer or url_for("dashboard"))
        ex("UPDATE requests SET status='Disapproved', remarks=?, returned_at=NULL WHERE id=?", why[:300], rid); flash("Request disapproved.", "ok")
    elif action == "returned" and r["status"] == "Approved":
        ex("UPDATE requests SET returned_at=? WHERE id=?", now_s(), rid); flash("Marked as returned. Stock is available again.", "ok")
    else: abort(400)
    return redirect(url_for("dashboard", tab=request.form.get("back", "pending")))

@app.route("/admin/stock", methods=["POST"])
@admin_required
def admin_stock():
    n = request.form.get("name", "").strip()[:80]
    try: s = max(0, int(request.form.get("stock", "0")))
    except ValueError: s = -1
    if not n or s < 0: flash("Enter a valid name and quantity.", "err")
    else:
        ex("INSERT INTO inventory(name,stock) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET stock=excluded.stock", n, s)
        flash("Stock saved.", "ok")
    return redirect(url_for("dashboard", tab="stock"))

@app.route("/admin/user/<int:uid>/reset", methods=["POST"])
@admin_required
def admin_reset_user(uid):
    u = q1("SELECT * FROM users WHERE id=?", uid)
    if not u: abort(404)
    temp = secrets.token_urlsafe(6)
    ex("UPDATE users SET pw_hash=?, must_change=1 WHERE id=?", generate_password_hash(temp), uid)
    flash("Temporary password for %s: %s  (they must change it at next sign in)" % (u["username"], temp), "ok")
    return redirect(url_for("dashboard", tab="users"))

# ------------------------------------------------------------------ PDF
def make_pdf(r):
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=A4); H = 297 * mm
    its = q("SELECT name,qty FROM items WHERE request_id=?", r["id"]); fac = json.loads(r["facilities"] or "[]")
    def T(t, x, y, s=10, b=False, a="l", i=False):
        c.setFont("Helvetica-BoldOblique" if b and i else "Helvetica-Bold" if b else "Helvetica-Oblique" if i else "Helvetica", s)
        (c.drawCentredString if a == "c" else c.drawString)(x * mm, H - y * mm, str(t or ""))
    def L(x1, y, x2): c.line(x1 * mm, H - y * mm, x2 * mm, H - y * mm)
    def R(x, y, w, h): c.rect(x * mm, H - (y + h) * mm, w * mm, h * mm)
    def B(x, y, on):
        R(x, y - 3.5, 4, 4)
        if on: T("X", x + .8, y - .2, 9, True)
    for n, x in (("1", 28), ("2", 158)):
        c.drawImage(ImageReader(io.BytesIO(base64.b64decode(LOGOS[n]))), x * mm, H - 34 * mm, 24 * mm, 24 * mm)
    T("Southern Luzon State University", 105, 18, 13, True, "c"); T("Judge Guillermo Eleazar", 105, 23, 11, True, "c")
    T("GENERAL SERVICES OFFICE", 105, 28, 9, False, "c"); T("Tagkawayan, Quezon", 105, 32, 8, False, "c")
    R(140, 35, 55, 9); T("R.F.U. No:", 142, 39, 8); T(r["rfu_no"], 150, 42.5, 10, True)
    T("REQUEST FOR FACILITY/EQUIPMENT USE", 105, 52, 12, True, "c")
    y = 62
    T("Requester's Name:", 15, y); T(r["requester"], 52, y - .5); L(50, y + 1, 120); T("Date:", 130, y); T(r["created_at"][:10], 142, y - .5); L(140, y + 1, 195); y += 8
    T("College/Department:", 15, y); T(r["dept"], 52, y - .5); L(50, y + 1, 120); y += 8
    T("Name/Type of Event:", 15, y); T(r["event"], 52, y - .5); L(50, y + 1, 195); y += 8
    T("Date of the Event:", 15, y); T(r["event_date"], 50, y - .5); L(48, y + 1, 100)
    T("Estimated Attendees:", 110, y); T(r["attendees"], 148, y - .5); L(146, y + 1, 195); y += 8
    T("Time Reserved:", 15, y); T(r["t1"], 45, y - .5); L(43, y + 1, 70); T("to", 74, y); T(r["t2"], 82, y - .5); L(80, y + 1, 108); y += 9
    T("Facility to be used:", 15, y, 10, True); y += 7
    B(25, y, FACILITIES[0] in fac); T(FACILITIES[0], 31, y, 9); B(100, y, FACILITIES[1] in fac); T(FACILITIES[1], 106, y, 9); y += 7
    B(25, y, FACILITIES[2] in fac); T(FACILITIES[2], 31, y, 9); B(100, y, FACILITIES[3] in fac); T(FACILITIES[3], 106, y, 9); y += 7
    o = ", ".join(x for x in fac if x not in FACILITIES); B(25, y, bool(o)); T("others:", 31, y, 9); T(o, 46, y - .5, 9); L(44, y + 1, 120); y += 9
    T("Equipment:", 15, y, 10, True)
    lines = simpleSplit(", ".join("%s (%d)" % (i["name"], i["qty"]) for i in its) or "None", "Helvetica", 10, 150 * mm)
    for k, ln in enumerate(lines): T(ln, 40, y + 5 * k)
    L(38, y + 1, 195); y += 5 * len(lines) + 5
    T("Requested by:", 15, y, 8); y += 12; T(r["head"], 60, y - 1, 10, True, "c"); L(30, y, 90)
    T("College Department/Department Head", 60, y + 4, 8, False, "c"); y += 12
    R(15, y, 180, 22); c.line(105 * mm, H - y * mm, 105 * mm, H - (y + 22) * mm); T("Recommending Approval", 17, y + 5, 9)
    R(120, y + 1.5, 4, 4); T("X" if r["status"] == "Approved" else "", 120.8, y + 4.8, 9, True); T("Approved", 126, y + 5, 9)
    R(155, y + 1.5, 4, 4); T("X" if r["status"] == "Disapproved" else "", 155.8, y + 4.8, 9, True); T("Disapproved", 161, y + 5, 9)
    T("LUALHATI G. AGUILA", 60, y + 14, 9, True, "c"); T("Head, Business Affairs Office", 60, y + 19, 8, False, "c")
    T("RASELIETO B. GARCIA", 150, y + 14, 9, True, "c"); T("Head, General Services Office", 150, y + 19, 8, False, "c"); y += 30
    T("After Facility/Equipment Used:", 15, y, 9, True); y += 7; T("Findings/Observation/Recommendation:", 15, y, 9)
    note = (r["remarks"] or "") + ("  |  Returned: " + r["returned_at"] if r["returned_at"] else "")
    for k, ln in enumerate(simpleSplit(note, "Helvetica", 8, 175 * mm)[:2]): T(ln, 17, y + 6.5 + 8 * k, 8)
    L(15, y + 8, 195); L(15, y + 16, 195); y += 30
    T("Checked by:", 20, y); T("Noted:", 120, y); y += 14; L(20, y, 80); L(115, y, 195)
    T("GSO Supervisor", 50, y + 5, 9, False, "c"); T("RASELIETO B. GARCIA", 155, y - 1, 9, True, "c"); T("Head, General Services Office", 155, y + 5, 9, False, "c"); y += 14
    for k, ln in enumerate(["Note:", "  \u2022 Requester for the use of the facility is responsible for any damages.", "  \u2022 Please file three (3) days before the event.",
                            "  \u2022 Please attach any valid I.D. and contact number of requester for any purpose it may served."]):
        T(ln, 15, y + 4 * k, 8, True, "l", True)
    c.showPage(); c.save(); buf.seek(0); return buf

@app.route("/request/<int:rid>/pdf")
@login_required
def request_pdf(rid):
    r = q1("SELECT * FROM requests WHERE id=?", rid)
    if not r or (g.user["role"] != "admin" and r["user_id"] != g.user["id"]): abort(404)
    return send_file(make_pdf(r), mimetype="application/pdf", download_name="RFU-%s.pdf" % r["rfu_no"])

# ------------------------------------------------------------------ templates
CSS = """
:root{--bg:#f3f5f9;--card:#fff;--tx:#1b2333;--mu:#5d6779;--pr:#14417b;--ac:#c9a227;--bd:#d9dfe9}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif}
header{background:#14417b;color:#fff;border-bottom:4px solid var(--ac);padding:12px 20px;display:flex;align-items:center;gap:12px;justify-content:space-between;flex-wrap:wrap}
.br{display:flex;align-items:center;gap:10px}header h1{font:600 16px Georgia,serif;margin:0}header small{opacity:.8;display:block;font-size:12px}
header a,header button.lk{color:#fff;background:none;border:0;padding:0;font:inherit;cursor:pointer;text-decoration:underline;margin:0}
.wrap{max-width:980px;margin:22px auto;padding:0 16px}.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:22px;margin-bottom:18px}
h2{font:600 19px Georgia,serif;margin:0 0 14px;color:var(--pr)}label{display:block;font-size:13px;color:var(--mu);margin:10px 0 3px}
input,select{width:100%;padding:9px 10px;border:1px solid var(--bd);border-radius:6px;background:var(--bg);color:var(--tx);font:inherit}
input[type=checkbox]{width:auto;margin-right:6px}.g{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}@media(max-width:600px){.g{grid-template-columns:1fr}}
button,.btn{background:var(--pr);color:#fff;border:0;padding:8px 14px;border-radius:6px;font:600 14px inherit;cursor:pointer;margin:8px 6px 0 0;text-decoration:none;display:inline-block}
button.s,.btn.s{background:transparent;color:var(--pr);border:1px solid var(--pr)}button.r{background:#a63232}button.gr{background:#2b7a47}button.sm{padding:4px 9px;font-size:12px;margin:2px 4px 2px 0}
a{color:var(--pr)}.ck label{display:inline-flex;align-items:center;margin:4px 16px 4px 0;color:var(--tx)}
.msg{padding:10px 14px;border-radius:6px;margin-bottom:14px}.msg.err{background:#f8d7d7;color:#8e2323}.msg.ok{background:#d5f0de;color:#1e6b3a}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px;border-bottom:1px solid var(--bd);vertical-align:top}th{color:var(--mu);font-weight:600}.tb{overflow-x:auto}
.b{padding:2px 9px;border-radius:12px;font-size:12px;font-weight:600;white-space:nowrap}.Pending{background:#fff1c9;color:#7a5a00}.Approved{background:#d5f0de;color:#1e6b3a}.Disapproved{background:#f8d7d7;color:#8e2323}.Returned{background:#dbe7fb;color:#14417b}
.tabs{display:flex;flex-wrap:wrap;margin-bottom:14px}.tabs a{margin:0 6px 6px 0;padding:8px 14px;border:1px solid var(--pr);border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;color:var(--pr)}.tabs a.on{background:var(--pr);color:#fff}
.auth{max-width:430px;margin:36px auto}.erow{display:flex;gap:8px;margin-bottom:6px}.erow select{flex:2}.erow input{flex:1}
.cal{width:100%;table-layout:fixed}.cal td,.cal th{border:1px solid var(--bd);height:74px;padding:3px;font-size:11px;overflow:hidden}.cal th{height:auto;text-align:center}
.cal i{display:block;font-style:normal;color:#fff;border-radius:3px;padding:0 4px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.cal i.Approved{background:var(--pr)}.cal i.Pending{background:#c9a227}
form.in{display:inline}.mu{color:var(--mu);font-size:12px}
"""
T = {}
T["base.html"] = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Facility &amp; Equipment Request - SLSU</title><style>""" + CSS + """</style></head><body>
<header><div class="br"><img src="{{ url_for('logo', n='1') }}" height="46" alt=""><img src="{{ url_for('logo', n='2') }}" height="46" alt="">
<div><h1>Southern Luzon State University - Judge Guillermo Eleazar</h1><small>General Services Office - Facility &amp; Equipment Request</small></div></div>
{% if g.user %}<div style="font-size:13px">{{ g.user.fullname }} ({{ g.user.role }}) &middot; <a href="{{ url_for('account') }}">Change password</a> &middot;
<form class="in" method="post" action="{{ url_for('logout') }}"><input type="hidden" name="_csrf" value="{{ csrf() }}"><button class="lk">Sign out</button></form></div>{% endif %}</header>
<div class="wrap">{% for c, m in get_flashed_messages(with_categories=true) %}<div class="msg {{ c }}">{{ m }}</div>{% endfor %}{% block body %}{% endblock %}</div></body></html>"""
T["macros.html"] = """
{% macro tabs(items, tab) %}<div class="tabs">{% for k, label in items %}<a class="{{ 'on' if tab == k }}" href="{{ url_for('dashboard', tab=k) }}">{{ label }}</a>{% endfor %}</div>{% endmacro %}
{% macro token() %}<input type="hidden" name="_csrf" value="{{ csrf() }}">{% endmacro %}
{% macro table(rows, admin=False, tab='') %}<div class="card"><div class="tb"><table><tr><th>RFU No.</th>{% if admin %}<th>Requester</th>{% endif %}<th>Event</th><th>Date &amp; time</th><th>Resources</th><th>Status</th><th>Actions</th></tr>
{% for r in rows %}<tr><td>{{ r.rfu_no }}</td>{% if admin %}<td>{{ r.requester }}<br><span class="mu">{{ r.dept }}</span></td>{% endif %}
<td>{{ r.event }}</td><td>{{ r.event_date }}<br><span class="mu">{{ r.t1 }} - {{ r.t2 }}</span></td><td><span class="mu" style="font-size:13px">{{ r.res }}</span></td>
<td><span class="b {{ r.badge }}">{{ r.badge }}</span>{% if r.status == 'Approved' and not r.returned_at and r.its %}<br><span class="mu">Not yet returned</span>{% endif %}
{% if r.returned_at %}<br><span class="mu">{{ r.returned_at }}</span>{% endif %}{% if r.remarks %}<br><span class="mu">Remarks: {{ r.remarks }}</span>{% endif %}</td>
<td><a href="{{ url_for('request_pdf', rid=r.id) }}">PDF</a>
{% if admin %}<br>{% if r.status != 'Approved' %}<form class="in" method="post" action="{{ url_for('admin_action', rid=r.id, action='approve') }}">{{ token() }}<input type="hidden" name="back" value="{{ tab }}"><button class="sm gr">Approve</button></form>{% endif %}
{% if r.status == 'Approved' and not r.returned_at %}<form class="in" method="post" action="{{ url_for('admin_action', rid=r.id, action='returned') }}">{{ token() }}<input type="hidden" name="back" value="{{ tab }}"><button class="sm">{{ 'Mark Returned' if r.its else 'Mark Completed' }}</button></form>{% endif %}
{% if r.status != 'Disapproved' %}<form method="post" action="{{ url_for('admin_action', rid=r.id, action='disapprove') }}">{{ token() }}<input type="hidden" name="back" value="{{ tab }}"><input name="remarks" placeholder="Reason (required)" required style="padding:4px;font-size:12px;margin-top:4px"><button class="sm r">Disapprove</button></form>{% endif %}{% endif %}</td></tr>
{% else %}<tr><td colspan="7">No requests.</td></tr>{% endfor %}</table></div></div>{% endmacro %}
{% macro calendar(weeks, days, title, prev, next, tab) %}<div class="card"><h2>Booking Calendar</h2>
<div style="display:flex;justify-content:space-between;align-items:center"><a class="btn s" href="{{ url_for('dashboard', tab=tab, m=prev) }}">&lsaquo;</a><b>{{ title }}</b><a class="btn s" href="{{ url_for('dashboard', tab=tab, m=next) }}">&rsaquo;</a></div>
<table class="cal" style="margin-top:8px"><tr>{% for d in ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'] %}<th>{{ d }}</th>{% endfor %}</tr>
{% for w in weeks %}<tr>{% for d in w %}<td>{% if d %}{{ d }}{% for r in days.get(d, []) %}<i class="{{ r.status }}" title="{{ r.event }} ({{ r.t1 }}-{{ r.t2 }}): {{ r.res }}">{{ r.t1 }} {{ r.res }}</i>{% endfor %}{% endif %}</td>{% endfor %}</tr>{% endfor %}</table>
<p class="mu">Navy = Approved &middot; Gold = Pending. Hover an entry for details.</p></div>{% endmacro %}"""
T["login.html"] = """{% extends 'base.html' %}{% block body %}{% import 'macros.html' as m %}<form class="card auth" method="post"><h2>Sign In</h2>{{ m.token() }}
<label>Username</label><input name="username" autofocus required><label>Password</label><input name="password" type="password" required>
<button>Sign In</button><p><a href="{{ url_for('signup') }}">Create an account</a> &middot; <a href="{{ url_for('forgot') }}">Forgot password?</a></p></form>{% endblock %}"""
T["signup.html"] = """{% extends 'base.html' %}{% block body %}{% import 'macros.html' as m %}<form class="card auth" method="post"><h2>Sign Up</h2>{{ m.token() }}
<label>Full name</label><input name="fullname" required><label>Student number</label><input name="student_no" required><label>Username</label><input name="username" required>
<label>Password (min. 8 characters)</label><input name="password" type="password" required><label>Confirm password</label><input name="confirm" type="password" required>
<button>Create Account</button><a class="btn s" href="{{ url_for('login') }}">Back</a></form>{% endblock %}"""
T["forgot.html"] = """{% extends 'base.html' %}{% block body %}{% import 'macros.html' as m %}<form class="card auth" method="post"><h2>Forgot Password</h2>{{ m.token() }}
<p class="mu">Enter the details you registered with to verify your identity. Admin accounts must be reset on the server.</p>
<label>Username</label><input name="username" required><label>Full name</label><input name="fullname" required><label>Student number</label><input name="student_no" required>
<label>New password (min. 8 characters)</label><input name="password" type="password" required><label>Confirm new password</label><input name="confirm" type="password" required>
<button>Reset Password</button><a class="btn s" href="{{ url_for('login') }}">Back</a></form>{% endblock %}"""
T["account.html"] = """{% extends 'base.html' %}{% block body %}{% import 'macros.html' as m %}<form class="card auth" method="post"><h2>Change Password</h2>{{ m.token() }}
<label>Current password</label><input name="current" type="password" required><label>New password (min. 8 characters)</label><input name="password" type="password" required>
<label>Confirm new password</label><input name="confirm" type="password" required><button>Update Password</button>{% if not g.user.must_change %}<a class="btn s" href="{{ url_for('dashboard') }}">Cancel</a>{% endif %}</form>{% endblock %}"""
T["student.html"] = """{% extends 'base.html' %}{% block body %}{% import 'macros.html' as m %}
{{ m.tabs([('new','New Request'),('mine','My Requests (' ~ mine|length ~ ')'),('cal','Calendar')], tab) }}
{% if tab == 'new' %}<form class="card" method="post" action="{{ url_for('new_request') }}"><h2>Request for Facility/Equipment Use</h2>{{ m.token() }}<div class="g">
<div><label>Requester's name *</label><input name="requester" value="{{ g.user.fullname }}" required></div><div><label>Date</label><input value="{{ today }}" disabled></div>
<div><label>College/Department *</label><input name="dept" required></div><div><label>Name/Type of event *</label><input name="event" required></div>
<div><label>Date of the event *</label><input id="ed" name="event_date" type="date" min="{{ today }}" required></div><div><label>Estimated attendees (optional)</label><input name="attendees" type="number" min="0"></div>
<div><label>Time reserved - from *</label><input id="t1" name="t1" type="time" required></div><div><label>to *</label><input id="t2" name="t2" type="time" required></div></div>
<label>Facility to be used</label><div class="ck">{% for f in facilities %}<label><input type="checkbox" class="fc" name="fac" value="{{ f }}"><span>{{ f }}</span></label>{% endfor %}</div>
<input name="fac_other" placeholder="Others (specify)"><label>Equipment</label><div id="eq"></div><button type="button" class="s" onclick="addEq()">+ Add equipment</button>
<label>Requested by (College Department/Department Head) - optional</label><input name="head">
<p class="mu">Note: The requester is responsible for any damages. Please attach a valid I.D. and contact number when the form is printed. Availability updates after you pick the event date and time. Equipment that was borrowed and not yet returned is not available.</p>
<button>Submit Request</button></form>
<script>
const INV={{ inv|tojson }};let AV={left:{},booked:[]};const $=s=>document.querySelector(s);
function addEq(){const d=document.createElement('div');d.className='erow';
 d.innerHTML='<select name="item_name" onchange="paint()">'+INV.map(n=>'<option value="'+n.replace(/"/g,'&quot;')+'"></option>').join('')+'<option value="__other">Other (type name)</option></select><input name="item_qty" type="number" min="1" value="1" onchange="paint()"><input name="item_other" placeholder="Equipment name" style="flex:2;display:none"><button type="button" class="r" style="margin:0" onclick="this.parentNode.remove()">x</button>';
 $('#eq').appendChild(d);paint()}
async function refresh(){try{AV=await (await fetch('/api/availability?d='+$('#ed').value+'&t1='+$('#t1').value+'&t2='+$('#t2').value)).json()}catch(e){}paint()}
function paint(){document.querySelectorAll('.fc').forEach(c=>{const b=AV.booked.includes(c.value.toLowerCase());c.disabled=b;if(b)c.checked=false;c.nextElementSibling.textContent=c.value+(b?' (booked)':'')});
 document.querySelectorAll('.erow').forEach(r=>{const s=r.querySelector('select'),q=r.querySelector('[name=item_qty]');
  [...s.options].forEach(o=>{if(o.value==='__other')return;const l=AV.left[o.value];o.disabled=!(l>0);o.textContent=o.value+(l>0?' ('+l+' available)':' (out of stock)')});
  if(s.selectedOptions[0].disabled){const f=[...s.options].find(o=>!o.disabled);if(f)s.value=f.value}
  const oth=s.value==='__other';r.querySelector('[name=item_other]').style.display=oth?'block':'none';
  if(oth)q.removeAttribute('max');else{const l=AV.left[s.value]||0;q.max=l;if(+q.value>l)q.value=Math.max(l,1)}})}
['ed','t1','t2'].forEach(i=>$('#'+i).addEventListener('change',refresh));addEq();refresh();
</script>
{% elif tab == 'mine' %}{{ m.table(mine) }}
{% else %}{{ m.calendar(weeks, days, title, prev, next, 'cal') }}{% endif %}{% endblock %}"""
T["admin.html"] = """{% extends 'base.html' %}{% block body %}{% import 'macros.html' as m %}
{{ m.tabs([('pending','Pending (' ~ cnt.pending ~ ')'),('approved','Approved (' ~ cnt.approved ~ ')'),('returned','Returned (' ~ cnt.returned ~ ')'),('disapproved','Disapproved (' ~ cnt.disapproved ~ ')'),('cal','Calendar'),('stock','Equipment Stock'),('users','Users')], tab) }}
{% if tab in ('pending','approved','returned','disapproved') %}{% if tab == 'approved' %}<p class="mu">Approved requests stay here until you click <b>Mark Returned</b>. Unreturned items stay out of stock, even after the event date.</p>{% endif %}{{ m.table(rows, True, tab) }}
{% elif tab == 'cal' %}{{ m.calendar(weeks, days, title, prev, next, 'cal') }}
{% elif tab == 'stock' %}<div class="card"><h2>Equipment Stock</h2><p class="mu">Set the total quantity you own. Students cannot borrow more than what is left for their chosen date and time. "Out now" = approved and not yet returned.</p>
<table><tr><th>Equipment</th><th>Out now (not returned)</th><th>Available now</th><th>Total stock</th></tr>{% for i in inv %}
<tr><td>{{ i.name }}</td><td>{{ i.out }}</td><td>{{ [i.stock - i.out, 0]|max }}</td><td><form class="in" method="post" action="{{ url_for('admin_stock') }}">{{ m.token() }}<input type="hidden" name="name" value="{{ i.name }}"><input name="stock" type="number" min="0" value="{{ i.stock }}" style="max-width:100px;display:inline-block"><button class="sm">Save</button></form></td></tr>{% endfor %}</table>
<form method="post" action="{{ url_for('admin_stock') }}" class="erow" style="margin-top:14px">{{ m.token() }}<input name="name" placeholder="New equipment name" required><input name="stock" type="number" min="0" placeholder="Stock" required><button style="margin:0">Add</button></form></div>
{% else %}<div class="card"><h2>Users</h2><div class="tb"><table><tr><th>Name</th><th>Student no.</th><th>Username</th><th>Role</th><th></th></tr>{% for u in users %}
<tr><td>{{ u.fullname }}</td><td>{{ u.student_no }}</td><td>{{ u.username }}</td><td>{{ u.role }}</td><td>{% if u.id != g.user.id %}<form class="in" method="post" action="{{ url_for('admin_reset_user', uid=u.id) }}" onsubmit="return confirm('Reset password for {{ u.username }}?')">{{ m.token() }}<button class="sm">Reset password</button></form>{% endif %}</td></tr>{% endfor %}</table></div></div>{% endif %}{% endblock %}"""
app.jinja_loader = DictLoader(T)
app.jinja_env.globals["csrf"] = csrf

init_db()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset-admin":
        with app.app_context():
            pw = os.environ.get("RFU_ADMIN_PASSWORD", "admin123")
            ex("UPDATE users SET pw_hash=?, must_change=1 WHERE username='admin'", generate_password_hash(pw))
        print("Admin password reset to '%s' (must be changed at next login)." % pw)
    else:
        app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)