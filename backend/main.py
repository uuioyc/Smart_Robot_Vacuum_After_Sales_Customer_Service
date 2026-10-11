import json
import os
import sys
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware   # ← 加到顶部 import 区

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from agent.react_agent import ReactAgent


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"], #前端地址
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
"""
为什么 allow_credentials=True 时，allow_origins 不能是 *
这是浏览器的安全策略。* 表示任何网站都可以访问，
credentials 表示携带用户的 Cookie 和认证信息。两个组合在一起，恶意网站就能利用用户的登录状态去请求目标 API，造成 CSRF 攻击。
"""
agent = ReactAgent()

class ChatRequest(BaseModel):
    message: str
    session_id: str
    history: Optional[list[dict[str, str]]] = []
    #dict[str,str]前一个str是键的类型，后一个是值的类型
@app.get("/")
def root():
    return {"message": "Hello, Agent API!"}

@app.post("/api/chat")
def chat(req: ChatRequest):
    def event_stream():
        for chunk in agent.execute_stream(
                req.message,
                session_id=req.session_id,
                history=req.history
        ):
            yield f"data: {json.dumps({'content':chunk}, ensure_ascii=False)}\n" #SSE格式
            #SSE是一种格式协议
        yield "data: [DONE]\n\n"
    return StreamingResponse( #流式返回通用工具
        event_stream(),
        media_type="text/event-stream" #必须这么写才能识别
    )
#yield 是产出一个值，yield from 是转发另一个生成器的所有产出
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)