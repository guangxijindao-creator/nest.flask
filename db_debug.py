import sqlite3

conn = sqlite3.connect("DATABASE")
cur = conn.cursor()

cur.execute("SELECT * FROM users")
print(cur.fetchall())

conn.close()
