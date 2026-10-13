"""
数据库配置：SQLite + SQLAlchemy
负责定义数据表结构、初始化数据库、提供数据库会话
"""
from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text

#SQLite数据库文件路径，放在backend下面
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATASET_URL = "sqlite:///./app.db"

engine = create_engine(
    SQLALCHEMY_DATASET_URL,
    #SQLite 默认不允许跨线程使用链接，FastApi是多线程的，所以要关掉这个限制
    connect_args={"check_same_thread":False}
)

#创建会话工厂：每次调用SessionLocal 得到一个数据库会话
SessionLocal = sessionmaker(autocommit=False,autoflush=False,bind=engine)

#所有数据表模型的基类
Base = declarative_base()

#定义数据表

class User(Base):
    """用户表"""
    __tablename__ = "user"
    #inde是索引，查询更快，但是占磁盘空间，插入更新慢，只给常用的建索引
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Session(Base):
    __tablename__ = "session"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    title = Column(String, default="新对话")
    created_at = Column(DateTime, default=datetime.now)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True, nullable=False)
    role = Column(String, nullable=False)
    content = Column(String, nullable=False)
    sources = Column(Text, default="[]")
    created_at = Column(DateTime, default=datetime.now)
def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    """
        FastAPI 依赖函数：每个请求分配一个数据库会话
        请求结束时自动关闭会话
        Depends 是 FastAPI 的依赖注入机制。
        一句话："这个接口需要什么，你就声明，FastAPI 帮你准备好。"
        def register(req: RegisterRequest, db: Session = Depends(get_db))
        db的生命周期交给fastapi管理
        不用重复写db的手动创建和关闭
        为什么用yield？
        因为yield产出以后还回来。return就不回来了，没办法关闭db
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()