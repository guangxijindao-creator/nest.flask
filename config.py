import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DATABASE = os.path.join(BASE_DIR, "users.db")
    WTF_CSRF_ENABLED = True        # 追加
    WTF_CSRF_TIME_LIMIT = None     # 追加