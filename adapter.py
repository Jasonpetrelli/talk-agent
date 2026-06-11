"""
WorkBuddy 适配层 - OpenAI 兼容接口，包装 ops_agent
启动: uvicorn adapter:app --host 0.0.0.0 --port 8080 --reload
"""

import time
from fastapi import FastAPI
from pydantic import BaseModel

from ops_agent import ops_agent

app = FastAPI(title="WorkBuddy Adapter")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "ops-agent"
    messages: list[Message]


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

    try:
        reply = ops_agent(user_msg)
    except Exception as e:
        reply = f"处理出错了：{e}"

    return _reply(reply, req.model)


@app.get("/health")
def health():
    return {"status": "ok", "service": "adapter", "port": 8080}


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