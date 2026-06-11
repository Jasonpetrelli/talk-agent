"""会话状态管理 - 使用文件存储，支持多进程"""
import time
import json
import os
from typing import Optional

# 会话存储文件
SESSION_FILE = os.path.join(os.path.dirname(__file__), ".sessions.json")

# 会话过期时间（秒）
SESSION_TTL = 300  # 5分钟


def _load_sessions() -> dict:
    """从文件加载会话"""
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_sessions(sessions: dict):
    """保存会话到文件"""
    with open(SESSION_FILE, "w") as f:
        json.dump(sessions, f)


def get_session(session_id: str) -> Optional[dict]:
    """获取会话状态"""
    sessions = _load_sessions()
    if session_id in sessions:
        session = sessions[session_id]
        if time.time() - session.get("timestamp", 0) < SESSION_TTL:
            return session
        else:
            del sessions[session_id]
            _save_sessions(sessions)
    return None


def set_session(session_id: str, data: dict):
    """设置会话状态"""
    sessions = _load_sessions()
    data["timestamp"] = time.time()
    sessions[session_id] = data
    _save_sessions(sessions)


def update_session(session_id: str, **kwargs):
    """更新会话状态"""
    sessions = _load_sessions()
    if session_id in sessions:
        sessions[session_id].update(kwargs)
        sessions[session_id]["timestamp"] = time.time()
    else:
        kwargs["timestamp"] = time.time()
        sessions[session_id] = kwargs
    _save_sessions(sessions)


def clear_session(session_id: str):
    """清除会话状态"""
    sessions = _load_sessions()
    if session_id in sessions:
        del sessions[session_id]
        _save_sessions(sessions)
