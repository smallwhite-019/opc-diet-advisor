# -*- coding: utf-8 -*-
"""SQLite 持久化：用户 / 会话 / 消息。零运维，满足多轮对话与历史持久化(进阶3)。"""
import os, sqlite3, datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diet_advisor.db")
_conn = None

def get_conn():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init()
    return _conn

def _init():
    c = _conn
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, nickname TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY, user_id TEXT, title TEXT, updated_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, conv_id TEXT, role TEXT,
        content TEXT, sources TEXT, created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS accounts (
        username TEXT PRIMARY KEY, password_hash TEXT, nickname TEXT, created_at TEXT)""")
    c.commit()

def ensure_user(uid, nickname=""):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO users(id, nickname, created_at) VALUES(?,?,?)",
                 (uid, nickname, _now()))
    conn.commit()

def update_nickname(uid, nickname):
    conn = get_conn()
    conn.execute("UPDATE users SET nickname=? WHERE id=?", (nickname, uid))
    conn.commit()

def get_user(uid):
    row = get_conn().execute("SELECT id,nickname,created_at FROM users WHERE id=?", (uid,)).fetchone()
    return dict(row) if row else None

def clear_user_data(uid):
    """清空该用户全部会话与消息（保留账号本身）。"""
    conn = get_conn()
    cids = [r["id"] for r in conn.execute("SELECT id FROM conversations WHERE user_id=?", (uid,)).fetchall()]
    for cid in cids:
        conn.execute("DELETE FROM messages WHERE conv_id=?", (cid,))
    conn.execute("DELETE FROM conversations WHERE user_id=?", (uid,))
    conn.commit()
    return len(cids)

def export_user_messages(uid):
    """导出该用户全部会话的消息，结构：[{conv_id, title, role, content, created_at}]。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT m.conv_id, c.title, m.role, m.content, m.created_at "
        "FROM messages m JOIN conversations c ON m.conv_id=c.id WHERE c.user_id=? "
        "ORDER BY c.updated_at DESC, m.id ASC", (uid,)).fetchall()
    return [dict(r) for r in rows]

def new_conversation(uid, title="新对话"):
    cid = f"c_{os.urandom(6).hex()}"
    get_conn().execute(
        "INSERT INTO conversations(id, user_id, title, updated_at) VALUES(?,?,?,?)",
        (cid, uid, title, _now()))
    get_conn().commit()
    return cid

def list_conversations(uid):
    rows = get_conn().execute(
        "SELECT id,title,updated_at FROM conversations WHERE user_id=? ORDER BY updated_at DESC",
        (uid,)).fetchall()
    return [dict(r) for r in rows]

def delete_conversation(cid):
    conn = get_conn()
    conn.execute("DELETE FROM messages WHERE conv_id=?", (cid,))
    conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
    conn.commit()

def add_message(cid, role, content, sources=""):
    get_conn().execute(
        "INSERT INTO messages(conv_id, role, content, sources, created_at) VALUES(?,?,?,?,?)",
        (cid, role, content, sources, _now()))
    get_conn().commit()

def get_history(cid, limit=10):
    rows = get_conn().execute(
        "SELECT role,content FROM messages WHERE conv_id=? ORDER BY id DESC LIMIT ?",
        (cid, limit)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_accounts_table():
    get_conn()

def get_account(username):
    row = get_conn().execute(
        "SELECT username, password_hash, nickname, created_at FROM accounts WHERE username=?",
        (username,)).fetchone()
    return dict(row) if row else None

def add_account(username, password_hash, nickname=""):
    get_conn().execute(
        "INSERT INTO accounts(username, password_hash, nickname, created_at) VALUES(?,?,?,?)",
        (username, password_hash, nickname, _now()))
    get_conn().commit()

def update_account_nickname(username, nickname):
    get_conn().execute(
        "UPDATE accounts SET nickname=? WHERE username=?", (nickname, username))
    get_conn().commit()

def get_account_nickname(username):
    row = get_conn().execute("SELECT nickname FROM accounts WHERE username=?", (username,)).fetchone()
    return row["nickname"] if row else ""
