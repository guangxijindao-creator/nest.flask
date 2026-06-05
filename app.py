
from flask import Flask, request, render_template, session, redirect
import sqlite3
import os
import psycopg2
import psycopg2.extras

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from datetime import datetime, timedelta
from functools import wraps

from config import Config
from flask_wtf.csrf import CSRFProtect

# .env 読み込み
load_dotenv()
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# config読み込み → SECRET_KEY設定 → CSRF初期化（この順番を守る）
app.config.from_object(Config)
app.secret_key = app.config["SECRET_KEY"]
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=30) 
csrf = CSRFProtect(app)


# =========================
# DB接続
# =========================

def get_db():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        conn = psycopg2.connect(database_url)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
    else:
        conn = sqlite3.connect(app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
    return conn


# =========================
# バリデーション
# =========================

def validate_event_input(title, pdf_link, max_participants, deadline):
    if not title or len(title.strip()) == 0:
        return "タイトルが空です"
    if not pdf_link:
        return "PDFリンクが空です"
    if not pdf_link.startswith("https://"):
        return "URLはhttpsから始まる必要があります"
    if not pdf_link.lower().endswith(".pdf"):
        return "PDFファイルのみ許可されています"
    try:
        int(max_participants)
    except:
        return "人数は数値で入力してください"
    if not deadline:
        return "締切が必要です"
    return None


# =========================
# ログイン確認（デコレータ）
# =========================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "username" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return decorated_function


# =========================
# 管理者確認
# =========================

def is_admin_user():
    if "username" not in session:
        return False
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT is_admin FROM users WHERE username=%s", (session["username"],))
    user = cur.fetchone()
    conn.close()
    return user and user["is_admin"] == 1


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_admin_user():
            return render_template("message.html", message="権限がありません", back_url="/mypage")
        return f(*args, **kwargs)
    return decorated_function


# =========================
# DB初期化
# =========================

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id SERIAL PRIMARY KEY,
        title TEXT,
        pdf_link TEXT,
        max_participants INTEGER,
        deadline TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        id SERIAL PRIMARY KEY,
        username TEXT,
        event_id INTEGER
    )
    """)
    conn.commit()
    conn.close()


# =========================
# 管理者作成
# =========================

def create_admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", ("admin",))
    admin_user = cur.fetchone()
    if not admin_user:
        cur.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (%s, %s, 1)",
            ("admin", generate_password_hash("nest_20060503"))
        )
        conn.commit()
    conn.close()


# 初期化実行
init_db()
create_admin()


# =========================
# トップページ
# =========================

@app.route("/")
def index():
    return render_template("index.html")


# =========================
# ユーザ登録
# =========================

@app.route("/register", methods=["POST"])
def register():
    username = request.form["username"]
    password = request.form["password"]
    password_confirm = request.form["password_confirm"]

    if password != password_confirm:
        return render_template("message.html", message="パスワードが一致しません", back_url="/")

    hashed_password = generate_password_hash(password)
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        conn.commit()
    except Exception as e:
        print(e)
        conn.close()
        return render_template("message.html", message="そのIDは既に存在します", back_url="/")
    conn.close()
    session["username"] = username
    return redirect("/mypage")


# =========================
# ログイン
# =========================

@app.route("/login", methods=["POST"])
def login():
    username = request.form["username"]
    password = request.form["password"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=%s", (username,))
    user = cur.fetchone()
    conn.close()
    if user and check_password_hash(user["password"], password):
        session["username"] = username
        return redirect("/mypage")
    return render_template("message.html", message="IDまたはパスワードが違います", back_url="/")


# =========================
# ログアウト
# =========================

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/")


# =========================
# マイページ
# =========================

@app.route("/mypage")
@login_required
def mypage():
    return render_template("mypage.html", username=session["username"], is_admin=is_admin_user())


# =========================
# 管理者ページ
# =========================

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin.html")


# =========================
# イベント作成画面
# =========================

@app.route("/create_event")
@admin_required
def create_event():
    return render_template("create_event.html")


# =========================
# イベント保存
# =========================

@app.route("/save_event", methods=["POST"])
@admin_required
def save_event():
    title = request.form["title"]
    pdf_link = request.form.get("pdf_link", "")
    max_participants = request.form["max_participants"]
    deadline = request.form["deadline"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO events (title, pdf_link, max_participants, deadline) VALUES (%s, %s, %s, %s)",
        (title, pdf_link, max_participants, deadline)
    )
    conn.commit()
    conn.close()
    return render_template("message.html", message="イベント作成成功", back_url="/admin_events")


# =========================
# イベント一覧
# =========================

@app.route("/events")
def events():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events")
    events = cur.fetchall()
    conn.close()
    return render_template("events.html", events=events)


# =========================
# ユーザー一覧
# =========================
@app.route("/admin_users")
@admin_required
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin FROM users ORDER BY id")
    users = cur.fetchall()
    conn.close()
    return render_template("admin_users.html", users=users)
# =========================
# イベント参加
# =========================

@app.route("/join_event", methods=["POST"])
@login_required
def join_event():
    event_id = request.form["event_id"]
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM participants WHERE username=%s AND event_id=%s",
        (session["username"], event_id)
    )
    if cur.fetchone():
        conn.close()
        return render_template("message.html", message="既に応募済みです", back_url="/events")

    cur.execute("SELECT COUNT(*) FROM participants WHERE event_id=%s", (event_id,))
    current_count = cur.fetchone()[0]

    cur.execute("SELECT max_participants, deadline FROM events WHERE id=%s", (event_id,))
    event = cur.fetchone()

    if not event:
        conn.close()
        return render_template("message.html", message="イベントが存在しません", back_url="/events")

    deadline = datetime.strptime(event["deadline"], "%Y-%m-%dT%H:%M")
    if datetime.now() > deadline:
        conn.close()
        return render_template("message.html", message="応募締切済みです", back_url="/events")

    if current_count >= event["max_participants"]:
        conn.close()
        return render_template("message.html", message="定員に達しています", back_url="/events")

    cur.execute("INSERT INTO participants (username, event_id) VALUES (%s, %s)", (session["username"], event_id))
    conn.commit()
    conn.close()
    return render_template("message.html", message="応募完了", back_url="/events")


# =========================
# 自分の参加イベント
# =========================

@app.route("/my_events")
@login_required
def my_events():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT events.id, events.title, events.pdf_link, events.deadline
        FROM participants
        JOIN events ON participants.event_id = events.id
        WHERE participants.username=%s
    """, (session["username"],))
    events = cur.fetchall()
    conn.close()
    return render_template("my_events.html", events=events)


# =========================
# 管理者イベント一覧
# =========================

@app.route("/admin_events")
@admin_required
def admin_events():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events")
    events = cur.fetchall()
    conn.close()
    return render_template("admin_events.html", events=events)


# =========================
# イベント編集画面
# =========================

@app.route("/edit_event/<int:event_id>")
@admin_required
def edit_event(event_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM events WHERE id=%s", (event_id,))
    event = cur.fetchone()
    conn.close()
    return render_template("edit_event.html", event=event)


# =========================
# イベント更新
# =========================

@app.route("/update_event", methods=["POST"])
@admin_required
def update_event():
    event_id = request.form["event_id"]
    title = request.form["title"]
    pdf_link = request.form.get("pdf_link", "")
    max_participants = request.form["max_participants"]
    deadline = request.form["deadline"]

    error = validate_event_input(title, pdf_link, max_participants, deadline)
    if error:
        return render_template("message.html", message=error, back_url="/admin_events")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        UPDATE events SET title=%s, pdf_link=%s, max_participants=%s, deadline=%s WHERE id=%s
    """, (title, pdf_link, int(max_participants), deadline, event_id))
    conn.commit()
    conn.close()
    return render_template("message.html", message="イベント更新成功", back_url="/admin_events")


# =========================
# イベント削除
# =========================

@app.route("/delete_event", methods=["POST"])
@admin_required
def delete_event():
    event_id = request.form["event_id"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM participants WHERE event_id=%s", (event_id,))
    cur.execute("DELETE FROM events WHERE id=%s", (event_id,))
    conn.commit()
    conn.close()
    return render_template("message.html", message="イベント削除成功", back_url="/admin_events")


# =========================
# 参加者一覧
# =========================

@app.route("/event_participants/<int:event_id>")
@admin_required
def event_participants(event_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT username FROM participants WHERE event_id=%s", (event_id,))
    participants = cur.fetchall()
    conn.close()
    return render_template("participants.html", participants=participants)




# =========================
# 起動
# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)