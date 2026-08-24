# -*- coding: utf-8 -*-
"""账号体系：注册 / 登录 / JWT 鉴权。
密码使用 bcrypt 哈希存储；登录后签发 JWT（HS256），后续接口通过 Authorization 头校验。
user_id 绑定登录账号，实现历史/档案按账号隔离。"""
import os, datetime, bcrypt, jwt
from fastapi import Header, HTTPException

SECRET = os.environ.get("JWT_SECRET") or "opc-diet-advisor-local-secret"
ALGO = "HS256"
TOKEN_EXP_DAYS = 30

# 用户表（账号体系，与原 users 表区分：accounts 存登录凭证）
import db
db.ensure_accounts_table()


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=TOKEN_EXP_DAYS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGO)


def register(username: str, password: str, nickname: str = ""):
    username = (username or "").strip()
    if len(username) < 3:
        raise ValueError("用户名至少 3 个字符")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")
    if db.get_account(username):
        raise ValueError("该用户名已存在")
    db.add_account(username, hash_password(password), nickname)
    return True


def login(username: str, password: str):
    acc = db.get_account(username)
    if not acc or not verify_password(password, acc["password_hash"]):
        raise ValueError("用户名或密码错误")
    return acc


def get_current_user(authorization: str = Header(None)):
    """FastAPI 依赖：从 Authorization: Bearer <token> 解析当前用户。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGO])
        username = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效令牌")
    if not username:
        raise HTTPException(status_code=401, detail="无效令牌")
    return username


def optional_user(authorization: str = Header(None)):
    """可选鉴权：有 token 返回 username，无则返回 None（用于兼容未登录）。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], SECRET, algorithms=[ALGO])
        return payload.get("sub")
    except Exception:
        return None
