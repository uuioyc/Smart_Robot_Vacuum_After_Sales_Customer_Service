import os
import sys
import json
import uvicorn
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware   # ← 加到顶部 import 区
from auth import hash_password, verify_password, create_access_token, decode_token
from database import User, init_db, get_db

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

#初始化数据库
init_db()

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    """认证响应：返回 token 和用户信息"""
    token: str
    user_id: int
    username: str

class ChatRequest(BaseModel):
    message: str
    session_id: str
    history: Optional[list[dict[str, str]]] = []
    #dict[str,str]前一个str是键的类型，后一个是值的类型

# ===== 认证依赖 =====
# HTTPBearer：从请求头 Authorization 里提取 "Bearer xxx"
security = HTTPBearer()

def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
) -> User:
    """
    从请求头的token里解析出当前用户
    这个函数是一个依赖，给需要登录的接口用
    :param credentials:
    :param db:
    :return:
    """
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的token"
        )

    user_id = int(payload['sub'])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在"
        )
    return user


@app.post("/api/register", response_model=TokenResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    注册接口
    - 检查用户名是否已存在
    - 创建用户
    - 返回 token（注册后直接登录，不用再登录一次）
    """
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    user = User(
        username = req.username,
        password_hash = hash_password(req.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user) #刷新拿到自增的id

    token = create_access_token(user.id, user.username)
    return TokenResponse(
        token = token,
        user_id = user.id,
        username = user.username
    )

@app.post("/api/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """
        登录接口
        - 查用户
        - 校验密码
        - 返回 token
    """
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    token = create_access_token(user.id, user.username)
    return TokenResponse(
        token=token,
        user_id=user.id,
        username=user.username
    )
@app.get("/")
def root():
    return {"message": "Hello, Agent API!"}

@app.post("/api/chat")
def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    def event_stream():
        for chunk in agent.execute_stream(
                req.message,
                session_id=req.session_id,
                history=req.history
        ):
            yield f"data: {json.dumps({'content':chunk}, ensure_ascii=False)}\n\n" #SSE格式
            #SSE是一种格式协议
        yield "data: [DONE]\n\n"
    return StreamingResponse( #流式返回通用工具
        event_stream(),
        media_type="text/event-stream" #必须这么写才能识别
    )
#yield 是产出一个值，yield from 是转发另一个生成器的所有产出
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)