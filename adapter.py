"""
WorkBuddy 适配层 - OpenAI 兼容接口，包装 ops_agent
启动: uvicorn adapter:app --host 0.0.0.0 --port 8080 --reload
"""

import base64
import hashlib
import os
import random
import struct
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from pydantic import BaseModel

from ops_agent import ops_agent

app = FastAPI(title="WorkBuddy Adapter")

STATIC_DIR = Path(__file__).parent
_ENV_LOADED = False


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "ops-agent"
    messages: list[Message]
    session_id: str = ""


class ChatResponse(BaseModel):
    id: str = "chatcmpl-xxx"
    object: str = "chat.completion"
    created: int
    model: str = ""
    choices: list[dict]
    usage: dict = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    user_msg = _extract_user_msg(req.messages)
    if not user_msg:
        return _reply("您好，请问有什么可以帮您？", req.model)

    # 使用 session_id，如果没有则用 default
    session_id = req.session_id or "default"

    try:
        reply = ops_agent(user_msg, session_id)
    except Exception as e:
        reply = f"处理出错了：{e}"

    return _reply(reply, req.model)


@app.get("/health")
def health():
    return {"status": "ok", "service": "adapter", "port": 8080}


@app.get("/wecom/callback", response_class=PlainTextResponse)
def wecom_verify(msg_signature: str, timestamp: str, nonce: str, echostr: str):
    """企业微信回调 URL 验证"""
    try:
        crypto = WeComCrypto.from_env()
        crypto.verify_signature(msg_signature, timestamp, nonce, echostr)
        return crypto.decrypt(echostr)
    except Exception as e:
        return PlainTextResponse(f"wecom verify failed: {e}", status_code=400)


@app.post("/wecom/callback")
async def wecom_callback(request: Request, msg_signature: str, timestamp: str, nonce: str):
    """接收企业微信文本消息并回复 agent 结果"""
    body = (await request.body()).decode("utf-8")
    try:
        crypto = WeComCrypto.from_env()
        encrypted = ET.fromstring(body).findtext("Encrypt") or ""
        crypto.verify_signature(msg_signature, timestamp, nonce, encrypted)
        plain_xml = crypto.decrypt(encrypted)
        msg = _parse_wecom_message(plain_xml)

        if msg["msg_type"] != "text":
            reply = "目前先支持文本询价。"
        else:
            reply = ops_agent(msg["content"], session_id=msg["from_user"])

        reply_xml = _build_wecom_text_reply(msg["to_user"], msg["from_user"], reply)
        encrypted_reply = crypto.encrypt(reply_xml)
        signature = crypto.signature(timestamp, nonce, encrypted_reply)
        response_xml = _build_wecom_encrypted_reply(encrypted_reply, signature, timestamp, nonce)
        return Response(content=response_xml, media_type="application/xml")
    except Exception as e:
        return PlainTextResponse(f"wecom callback failed: {e}", status_code=400)


def _extract_user_msg(messages: list[Message]) -> str:
    for m in reversed(messages):
        if m.role == "user":
            return m.content
    return ""


def _reply(content: str, model: str = "ops-agent") -> ChatResponse:
    return ChatResponse(
        created=int(time.time()),
        model=model,
        choices=[{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
    )


class WeComCrypto:
    def __init__(self, token: str, aes_key: str, corp_id: str):
        self.token = token
        self.corp_id = corp_id
        self.aes_key = base64.b64decode(aes_key + "=")

    @classmethod
    def from_env(cls):
        _load_env()
        token = os.getenv("WECOM_TOKEN", "")
        aes_key = os.getenv("WECOM_ENCODING_AES_KEY", "")
        corp_id = os.getenv("WECOM_CORP_ID", "")
        if not token or not aes_key or not corp_id:
            raise ValueError("请先在 .env 填写 WECOM_TOKEN / WECOM_ENCODING_AES_KEY / WECOM_CORP_ID")
        return cls(token, aes_key, corp_id)

    def signature(self, timestamp: str, nonce: str, encrypted: str) -> str:
        parts = sorted([self.token, timestamp, nonce, encrypted])
        return hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()

    def verify_signature(self, msg_signature: str, timestamp: str, nonce: str, encrypted: str):
        expected = self.signature(timestamp, nonce, encrypted)
        if expected != msg_signature:
            raise ValueError("签名校验失败")

    def decrypt(self, encrypted: str) -> str:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_key[:16]))
        decryptor = cipher.decryptor()
        plain = decryptor.update(base64.b64decode(encrypted)) + decryptor.finalize()
        plain = _pkcs7_unpad(plain)

        msg_len = struct.unpack("!I", plain[16:20])[0]
        msg = plain[20:20 + msg_len].decode("utf-8")
        receive_id = plain[20 + msg_len:].decode("utf-8")
        if receive_id != self.corp_id:
            raise ValueError("CorpID 校验失败")
        return msg

    def encrypt(self, plain_xml: str) -> str:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        random_bytes = "".join(str(random.randint(0, 9)) for _ in range(16)).encode("utf-8")
        msg = plain_xml.encode("utf-8")
        msg_len = struct.pack("!I", len(msg))
        plain = random_bytes + msg_len + msg + self.corp_id.encode("utf-8")
        plain = _pkcs7_pad(plain)

        cipher = Cipher(algorithms.AES(self.aes_key), modes.CBC(self.aes_key[:16]))
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(plain) + encryptor.finalize()
        return base64.b64encode(encrypted).decode("utf-8")


def _load_env():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    env_path = STATIC_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    _ENV_LOADED = True


def _parse_wecom_message(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    return {
        "to_user": root.findtext("ToUserName") or "",
        "from_user": root.findtext("FromUserName") or "",
        "msg_type": root.findtext("MsgType") or "",
        "content": (root.findtext("Content") or "").strip(),
    }


def _build_wecom_text_reply(to_user: str, from_user: str, content: str) -> str:
    safe_content = _cdata(content[:1800])
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{from_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{to_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{safe_content}]]></Content>"
        "</xml>"
    )


def _build_wecom_encrypted_reply(encrypted: str, signature: str, timestamp: str, nonce: str) -> str:
    return (
        "<xml>"
        f"<Encrypt><![CDATA[{encrypted}]]></Encrypt>"
        f"<MsgSignature><![CDATA[{signature}]]></MsgSignature>"
        f"<TimeStamp>{timestamp}</TimeStamp>"
        f"<Nonce><![CDATA[{nonce}]]></Nonce>"
        "</xml>"
    )


def _pkcs7_pad(data: bytes) -> bytes:
    block_size = 32
    pad_len = block_size - len(data) % block_size
    return data + bytes([pad_len]) * pad_len


def _pkcs7_unpad(data: bytes) -> bytes:
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 32:
        raise ValueError("非法填充")
    return data[:-pad_len]


def _cdata(text: str) -> str:
    return text.replace("]]>", "]]]]><![CDATA[>")
