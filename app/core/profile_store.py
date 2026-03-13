import os
import json
import time
from typing import Any, Dict

from app.utils import file_io

PROFILE_DIR = "memory/learner_profiles"

# Storage backend: "file" or "mysql"
PROFILE_STORE = os.getenv("PROFILE_STORE", "file").lower()

# MySQL config (used when PROFILE_STORE=mysql)
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "chattutor")


def _profile_path(user_id: str) -> str:
    safe_id = user_id or "anonymous"
    return os.path.join(PROFILE_DIR, f"{safe_id}.json")


def _default_profile(user_id: str) -> Dict[str, Any]:
    return {
        "learner_id": user_id,
        "updated_at": None,
        "cards": []
    }


def _mysql_connect():
    import pymysql  # optional dependency
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        autocommit=True,
    )


def _mysql_ensure_table(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS learner_profiles (
        user_id VARCHAR(64) PRIMARY KEY,
        profile_json JSON NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    ) CHARACTER SET utf8mb4
    """
    with conn.cursor() as cur:
        cur.execute(sql)


def load_profile(user_id: str) -> Dict[str, Any]:
    if PROFILE_STORE != "mysql":
        path = _profile_path(user_id)
        if not os.path.exists(path):
            return _default_profile(user_id)
        return file_io.load_json(path)

    try:
        conn = _mysql_connect()
        _mysql_ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT profile_json FROM learner_profiles WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
        conn.close()
        if not row:
            return _default_profile(user_id)
        data = row[0]
        if isinstance(data, str):
            return json.loads(data)
        return data
    except Exception:
        # fallback to file if MySQL unavailable
        path = _profile_path(user_id)
        if not os.path.exists(path):
            return _default_profile(user_id)
        return file_io.load_json(path)


def save_profile(profile: Dict[str, Any]) -> str:
    user_id = profile.get("learner_id") or "anonymous"
    profile["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    if PROFILE_STORE != "mysql":
        return file_io.save_json(profile, _profile_path(user_id))

    try:
        conn = _mysql_connect()
        _mysql_ensure_table(conn)
        payload = json.dumps(profile, ensure_ascii=False)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO learner_profiles (user_id, profile_json)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE profile_json=VALUES(profile_json)
                """,
                (user_id, payload),
            )
        conn.close()
        return "mysql"
    except Exception:
        # fallback to file
        return file_io.save_json(profile, _profile_path(user_id))
