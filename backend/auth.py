"""
JWT 认证模块
负责：密码哈希、密码校验、生成 token、解析 token
"""
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
# ===== 1. 配置 =====
# 签名密钥：用于给 token 签名，绝对不能泄露
# 生产环境要换成环境变量读取


SECRET_KEY = "1ceaf99939f7e9543fb16f9f13e7c96db0841432d892175ad9835c3b02dd72ca"

# 签名算法
ALGORITHM = "HS256"

#token有效期24小时
ACCESS_TOKEN_EXPIRE_MINUTES = 60*24

# ===== 2. 密码哈希工具 =====
# bcrypt：一种安全的密码哈希算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    #把哈希和明文对比
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: int, username: str) -> str:
    """
    生成JWT token
    输入：user_id=1, username='test'
    输出：一长串token
    :param user_id:
    :param username:
    :return:
    """
    #UTC 世界协调统一时间  python-jose 库内部验证 token 时用的是 UTC 时间。
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """
    解析token，返回payload
    如果token无效或者过期，抛异常
    :param token:
    :return:
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        return payload
    except JWTError:
        raise ValueError("无效的token")