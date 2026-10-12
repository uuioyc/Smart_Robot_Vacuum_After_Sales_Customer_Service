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
from database import User, init_db, get_db, Message, Session as ChatSession, SessionLocal

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
    session_id: Optional[int] = None
    history: Optional[list[dict[str, str]]] = []
    #dict[str,str]前一个str是键的类型，后一个是值的类型

class CreateSessionRequest(BaseModel):
    title: str = "新对话"

class SessionResponse(BaseModel):
    id: int
    title: str
    created_at: str
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

@app.get("/api/sessions") #查询所有会话
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == user.id
    ).order_by(ChatSession.created_at.desc()).all()
    return[
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat()
        }
        for s in sessions
    ]

@app.post("/api/sessions") #创建新会话
def create_session(
        req: CreateSessionRequest,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    session = ChatSession(
        user_id = user.id,
        title = req.title
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return{
        "id": session.id,
        "title": session.title,
        "created_at": session.created_at.isoformat()
    }

@app.delete("/api/sessions/{session_id}")
def delete_session(
        session_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """删除会话连带所有消息"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    #先删除消息再删除会话
    db.query(Message).filter(Message.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"message": "删除成功"}

@app.get("/api/sessions/{session_id}/messages")
def get_session_messages(
        session_id: int,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """获取某个会话的所有信息"""
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = db.query(Message).filter(
        Message.session_id == session_id
    ).order_by(Message.created_at.asc()).all()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content
        }
        for m in messages
    ]
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
def chat(
        req: ChatRequest,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    is_new_session = False
    if req.session_id is None:
        title = req.message[:20] if len(req.message) > 20 else req.message
        new_session = ChatSession(user_id = user.id, title = title)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        #提交后需要"数据库自动生成"的字段比如id，时间等 都需要refresh，从数据库重新读一遍。
        session_id = new_session.id
        is_new_session = True
    else:
        session = db.query(ChatSession).filter(
            ChatSession.id == req.session_id,
            ChatSession.user_id == user.id
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        session_id = req.session_id

    user_msg = Message(session_id = session_id, role = "user", content = req.message)
    db.add(user_msg)
    db.commit()
    def event_stream():
        full_response = ""
        inner_db = SessionLocal()
        """
            FastAPI 的 Depends(get_db) 有个特点：
            普通接口：db 在接口返回后自动关闭 
            StreamingResponse：生成器执行时，依赖可能已经"过期"或关闭
            表现：可能会报 Session is closed 或类似的错误。
            解决办法是在 event_stream 里重新创建一个 db 会话：
        """
        if is_new_session:
            yield f"data: {json.dumps({'type': 'session_id', 'session_id': session_id})}\n\n"
        for chunk in agent.execute_stream(
                req.message,
                session_id=str(session_id),
                history=req.history
        ):
            full_response += chunk
            yield f"data: {json.dumps({'content':chunk}, ensure_ascii=False)}\n\n" #SSE格式
            #SSE是一种格式协议
        ai_msg = Message(session_id = session_id, role = "assistant", content = full_response)
        inner_db.add(ai_msg)
        inner_db.commit()
        yield "data: [DONE]\n\n"
    return StreamingResponse( #流式返回通用工具
        event_stream(),
        media_type="text/event-stream" #必须这么写才能识别
    )
#yield 是产出一个值，yield from 是转发另一个生成器的所有产出
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)