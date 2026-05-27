from flask import Flask, request, render_template, session, redirect
import sqlite3

import secrets

from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime

app = Flask(__name__)

import os
app.config.from_object(Config)
def get_db():

    conn = sqlite3.connect("users.db")

    conn.row_factory = sqlite3.Row

    return conn

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

def login_required():

    if "username" not in session:
        return False

    return True

def create_admin():
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE username=?", ("admin",))
    if not cur.fetchone():

        cur.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (?, ?, 1)",
            ("admin", generate_password_hash('nest_20060503'))
        )

    conn.commit()
    conn.close()

def login_required():

    if "username" not in session:
        return False

    return True


# DB初期化
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

create_admin()

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():

    username = request.form["username"]
    password = request.form["password"]
    password_confirm = request.form["password_confirm"]

    # パスワード確認
    if password != password_confirm:
        return "パスワードが一致しません"

    hashed_password = generate_password_hash(password)

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, hashed_password)
        )

        conn.commit()

    except Exception as e:

        print(e)

        conn.close()

        return "そのIDは既に存在"

    conn.close()

    # 登録成功したら自動ログイン
    session["username"] = username

    return redirect("/mypage")

@app.route("/login", methods=["POST"])
def login():

    username = request.form["username"]
    password = request.form["password"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE username=?",
        (username,)
    )

    user = cur.fetchone()

    conn.close()

    if user and check_password_hash(user["password"], password):

        session["username"] = username

        return redirect("/mypage")

    else:
        return "IDまたはパスワードが違います"

@app.route("/mypage")
def mypage():

    if not login_required():
        return redirect("/")

    is_admin = is_admin_user()

    return render_template(
        "mypage.html",
        username=session["username"],
        is_admin=is_admin
    )
    
@app.route("/logout")
def logout():

    session.pop("username", None)

    return redirect("/")
    

@app.route("/admin")
def admin():

    if not is_admin_user():
        return render_template(
    "message.html",
    message="権限がありません",
    back_url="/mypage"
)

    return render_template("admin.html")

@app.route("/create_event")
def create_event():

    if "username" not in session:
        return redirect("/")

    if is_admin_user():
        return render_template("create_event.html")
    
    return render_template(
        "message.html",
        message="権限がありません",
        back_url="/mypage"
    )

@app.route("/save_event", methods=["POST"])
def save_event():

    if not is_admin_user():
        return "権限がありません"

    title = request.form["title"]
    pdf_link = request.form["pdf_link"]
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
        (title, pdf_link, max_participants, deadline)
    )

    conn.commit()
    conn.close()

    return """
    イベント作成成功<br>
    <a href='/mypage'>マイページへ戻る</a>
    """

@app.route("/edit_event/<int:event_id>")
def edit_event(event_id):

    if not login_required():
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    # 管理者確認
    cur.execute(
        "SELECT is_admin FROM users WHERE username=?",
        (session["username"],)
    )

    user = cur.fetchone()

    if not user or user["is_admin"] != 1:

        conn.close()

        return render_template(
    "message.html",
    message="権限がありません",
    back_url="/mypage"
)

    # イベント取得
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

@app.route("/update_event", methods=["POST"])
def update_event():

    if not login_required():
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    # 管理者確認
    cur.execute(
        "SELECT is_admin FROM users WHERE username=?",
        (session["username"],)
    )

    user = cur.fetchone()

    if not user or user["is_admin"] != 1:

        conn.close()

        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    event_id = request.form["event_id"]
    title = request.form["title"]
    pdf_link = request.form["pdf_link"]
    max_participants = request.form["max_participants"]
    deadline = request.form["deadline"]

    cur.execute(
        """
        UPDATE events
        SET title=?,
            pdf_link=?,
            max_participants=?,
            deadline=?
        WHERE id=?
        """,
        (
            title,
            pdf_link,
            max_participants,
            deadline,
            event_id
        )
    )

    conn.commit()
    conn.close()

    return """
    イベント更新成功<br>
    <a href='/admin_events'>イベント一覧へ戻る</a>
    """

@app.route("/delete_event", methods=["POST"])
def delete_event():

    if not login_required():
        return redirect("/")

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

@app.route("/join_event", methods=["POST"])
def join_event():

    if not login_required():
        return redirect("/")

    event_id = request.form["event_id"]

    conn = get_db()
    cur = conn.cursor()

    # 重複応募確認
    cur.execute(
        """
        SELECT * FROM participants
        WHERE username=? AND event_id=?
        """,
        (session["username"], event_id)
    )

    already_joined = cur.fetchone()

    if already_joined:

        conn.close()

        return render_template(
    "message.html",
    message="既に応募済みです",
    back_url="/events"
)
    # 参加人数確認
    cur.execute(
        """
        SELECT COUNT(*)
        FROM participants
        WHERE event_id=?
        """,
        (event_id,)
    )

    current_count = cur.fetchone()[0]

    # イベント情報取得
    cur.execute(
        """
        SELECT max_participants, deadline
        FROM events
        WHERE id=?
        """,
        (event_id,)
    )

    event = cur.fetchone()

    max_participants = event[0]

    deadline_str = event[1]

    # datetime変換
    deadline = datetime.strptime(
        deadline_str,
        "%Y-%m-%dT%H:%M"
    )

    now = datetime.now()

    # 締切判定
    if now > deadline:

        conn.close()

        return render_template(
    "message.html",
    message="応募締切済みです",
    back_url="/events"
)

    # 定員判定
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
        (session["username"], event_id)
    )

    conn.commit()
    conn.close()
    return render_template(
    "message.html",
    message="応募完了",
    back_url="/events"
)

@app.route("/my_events")
def my_events():

    if not login_required():
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT events.id, events.title, events.pdf_link, events.deadline
        FROM participants
        JOIN events ON participants.event_id = events.id
        WHERE participants.username=?
    """, (session["username"],))

    my_events = cur.fetchall()

    conn.close()

    return render_template("my_events.html", events=my_events)

@app.route("/admin_events")
def admin_events():

    if not login_required():
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE username=?", (session["username"],))
    user = cur.fetchone()

    if not user or user["is_admin"] != 1:
        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    cur.execute("SELECT * FROM events")
    events = cur.fetchall()

    conn.close()

    return render_template("admin_events.html", events=events)

@app.route("/event_participants/<int:event_id>")
def event_participants(event_id):

    if not login_required():
        return redirect("/")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT is_admin FROM users WHERE username=?", (session["username"],))
    user = cur.fetchone()

    if not user or user["is_admin"] != 1:
        return render_template(
            "message.html",
            message="権限がありません",
            back_url="/mypage"
        )

    cur.execute("""
        SELECT username
        FROM participants
        WHERE event_id=?
    """, (event_id,))

    participants = cur.fetchall()

    conn.close()

    return render_template("participants.html", participants=participants)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)