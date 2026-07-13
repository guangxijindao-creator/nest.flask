

from flask import Flask, request, render_template, session, redirect
import sqlite3
import os

from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime
from functools import wraps

from config import Config

from flask_wtf.csrf import CSRFProtect

# .env 読み込み
load_dotenv()
from werkzeug.middleware.proxy_fix import ProxyFix 
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1) 
app.config["WTF_CSRF_ENABLED"] = False
app.config["WTF_CSRF_TIME_LIMIT"] = None
# config.py 読み込み
app.config.from_object(Config)

# SECRET_KEY
app.secret_key = app.config["SECRET_KEY"]
# CSRF対策
csrf = CSRFProtect(app)
# =========================
# DB接続
# =========================

@app.route("/debug_db")
def debug_db():
    import sqlite3
    import os

    path = app.config["DATABASE"]

    conn = sqlite3.connect(path)
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()

    cur.execute("SELECT * FROM users")
    users = cur.fetchall()

    return {
        "db_path": path,
        "cwd": os.getcwd(),
        "tables": str(tables),
        "users": str(users)
    }

def get_db():

    conn = sqlite3.connect(app.config["DATABASE"])

    # user["username"] のように使える
    conn.row_factory = sqlite3.Row

    return conn

def validate_event_input(title, pdf_link, max_participants, deadline):
    
    # title
    if not title or len(title.strip()) == 0:
        return "タイトルが空です"

    # pdf
    if not pdf_link:
        return "PDFリンクが空です"

    if not pdf_link.startswith("https://"):
        return "URLはhttpsから始まる必要があります"

    if not pdf_link.lower().endswith(".pdf"):
        return "PDFファイルのみ許可されています"

    # max participants
    try:
        int(max_participants)
    except:
        return "人数は数値で入力してください"

    # deadline
    if not deadline:
        return "締切が必要です"

    return None
# =========================
# ログイン確認
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

    cur.execute(
        "SELECT is_admin FROM users WHERE username=?",
        (session["username"],)
    )

    user = cur.fetchone()

    conn.close()

    return user and user["is_admin"] == 1

def admin_required(f):

    @wraps(f)
    def decorated_function(*args, **kwargs):

        if not is_admin_user():

            return render_template(
                "message.html",
                message="権限がありません",
                back_url="/mypage"
            )

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
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        is_admin INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        pdf_link TEXT,
        max_participants INTEGER,
        deadline TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    cur.execute(
        "SELECT * FROM users WHERE username=?",
        ("admin",)
    )

    admin_user = cur.fetchone()

    if not admin_user:

        cur.execute(
            """
            INSERT INTO users
            (username, password, is_admin)
            VALUES (?, ?, 1)
            """,
            (
                "admin",
                generate_password_hash("nest_20060503")
            )
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
# ユーザ登録（名前のみ／既存なら再ログイン）
# =========================

@app.route("/register", methods=["POST"])
def register():

    username = request.form.get("username", "").strip()

    if not username:
        return render_template(
            "message.html",
            message="お名前を入力してください",
            back_url="/"
        )

    conn = get_db()
    cur = conn.cursor()

    # 既存ユーザーか確認
    cur.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    )
    existing_user = cur.fetchone()

    if not existing_user:

        try:
            cur.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, None)
            )
            conn.commit()

        except Exception as e:
            print(e)
            conn.close()
            return render_template(
                "message.html",
                message="登録に失敗しました",
                back_url="/"
            )

    conn.close()

    # 自動ログイン
    session["username"] = username

    return redirect("/mypage")


# =========================
# 管理者ログイン（一般公開はしない専用ルート）
# =========================

@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():

    if request.method == "GET":
        return render_template("admin_login.html")

    username = request.form["username"]
    password = request.form["password"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cur.fetchone()

    conn.close()

    if user and user["password"] and check_password_hash(user["password"], password):
        session["username"] = username
        return redirect("/mypage")

    return render_template("message.html", message="NG", back_url="/admin_login")

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
    return render_template(
        "mypage.html",
        username=session["username"],
        is_admin=is_admin_user()
    )

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
def create_event():

    if not is_admin_user():

        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    return render_template("create_event.html")


# =========================
# イベント保存
# =========================

@app.route("/save_event", methods=["POST"])
def save_event():

    if not is_admin_user():

        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    title = request.form["title"]
    pdf_link = request.form.get("pdf_link", "")
    max_participants = request.form["max_participants"]
    deadline = request.form["deadline"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO events
        (title, pdf_link, max_participants, deadline)
        VALUES (?, ?, ?, ?)
        """,
        (
            title,
            pdf_link,
            max_participants,
            deadline
        )
    )

    conn.commit()
    conn.close()

    return render_template(
        "message.html",
        message="イベント作成成功",
        back_url="/admin_events"
    )


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

    return render_template(
        "events.html",
        events=events
    )


# =========================
# イベント参加
# =========================

@app.route("/join_event", methods=["POST"])
@login_required
def join_event():
    event_id = request.form["event_id"]

    conn = get_db()
    cur = conn.cursor()

    # 重複確認
    cur.execute(
        """
        SELECT * FROM participants
        WHERE username=? AND event_id=?
        """,
        (
            session["username"],
            event_id
        )
    )

    already_joined = cur.fetchone()

    if already_joined:

        conn.close()

        return render_template(
            "message.html",
            message="既に応募済みです",
            back_url="/events"
        )

    # 現在人数
    cur.execute(
        """
        SELECT COUNT(*)
        FROM participants
        WHERE event_id=?
        """,
        (event_id,)
    )

    current_count = cur.fetchone()[0]

    # イベント取得
    cur.execute(
        """
        SELECT max_participants, deadline
        FROM events
        WHERE id=?
        """,
        (event_id,)
    )

    event = cur.fetchone()

    if not event:

        conn.close()

        return render_template(
            "message.html",
            message="イベントが存在しません",
            back_url="/events"
        )

    max_participants = event["max_participants"]

    deadline = datetime.strptime(
        event["deadline"],
        "%Y-%m-%dT%H:%M"
    )

    now = datetime.now()

    # 締切確認
    if now > deadline:

        conn.close()

        return render_template(
            "message.html",
            message="応募締切済みです",
            back_url="/events"
        )

    # 定員確認
    if current_count >= max_participants:

        conn.close()

        return render_template(
            "message.html",
            message="定員に達しています",
            back_url="/events"
        )

    # 応募登録
    cur.execute(
        """
        INSERT INTO participants
        (username, event_id)
        VALUES (?, ?)
        """,
        (
            session["username"],
            event_id
        )
    )

    conn.commit()
    conn.close()

    return render_template(
        "message.html",
        message="応募完了",
        back_url="/events"
    )


# =========================
# 自分の参加イベント
# =========================

@app.route("/my_events")
@login_required
def my_events():
    
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            events.id,
            events.title,
            events.pdf_link,
            events.deadline
        FROM participants
        JOIN events
        ON participants.event_id = events.id
        WHERE participants.username=?
        """,
        (session["username"],)
    )

    events = cur.fetchall()

    conn.close()

    return render_template(
        "my_events.html",
        events=events
    )


# =========================
# 管理者イベント一覧
# =========================

@app.route("/admin_events")
def admin_events():

    if not is_admin_user():

        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM events")

    events = cur.fetchall()

    conn.close()

    return render_template(
        "admin_events.html",
        events=events
    )


# =========================
# イベント編集画面
# =========================

@app.route("/edit_event/<int:event_id>")
def edit_event(event_id):

    if not is_admin_user():

        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM events WHERE id=?",
        (event_id,)
    )

    event = cur.fetchone()

    conn.close()

    return render_template(
        "edit_event.html",
        event=event
    )


# =========================
# イベント更新
# =========================

@app.route("/update_event", methods=["POST"])
def update_event():

    # -------------------------
    # 権限チェック
    # -------------------------
    if not is_admin_user():
        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    # -------------------------
    # 取得
    # -------------------------
    event_id = request.form["event_id"]
    title = request.form["title"]
    pdf_link = request.form.get("pdf_link", "")
    max_participants = request.form["max_participants"]
    deadline = request.form["deadline"]

    # -------------------------
    # バリデーション
    # -------------------------
    error = validate_event_input(
        title,
        pdf_link,
        max_participants,
        deadline
    )

    if error:
        return render_template(
            "message.html",
            message=error,
            back_url="/admin_events"
        )

    # -------------------------
    # DB更新（ここが抜けてた）
    # -------------------------
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE events
        SET title=?, pdf_link=?, max_participants=?, deadline=?
        WHERE id=?
    """, (
        title,
        pdf_link,
        int(max_participants),
        deadline,
        event_id
    ))

    conn.commit()
    conn.close()

    # -------------------------
    # 成功
    # -------------------------
    return render_template(
        "message.html",
        message="イベント更新成功",
        back_url="/admin_events"
    )
@app.route("/delete_event", methods=["POST"])
def delete_event():

    if not is_admin_user():

        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    event_id = request.form["event_id"]

    conn = get_db()
    cur = conn.cursor()

    # 参加情報削除
    cur.execute(
        "DELETE FROM participants WHERE event_id=?",
        (event_id,)
    )

    # イベント削除
    cur.execute(
        "DELETE FROM events WHERE id=?",
        (event_id,)
    )

    conn.commit()
    conn.close()

    return render_template(
        "message.html",
        message="イベント削除成功",
        back_url="/admin_events"
    )


# =========================
# 参加者一覧
# =========================

@app.route("/event_participants/<int:event_id>")
def event_participants(event_id):

    if not is_admin_user():

        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT username
        FROM participants
        WHERE event_id=?
        """,
        (event_id,)
    )

    participants = cur.fetchall()

    conn.close()

    return render_template(
        "participants.html",
        participants=participants
    )


# =========================
# 起動
# =========================

if __name__ == "__main__":
    import os
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )