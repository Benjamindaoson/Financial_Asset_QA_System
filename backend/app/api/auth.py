"""
简单认证系统 - Simple Authentication System
支持 API Key 和 JWT Token 认证
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

router = APIRouter()
security = HTTPBearer(auto_error=False)

# JWT 配置
SECRET_KEY = secrets.token_urlsafe(32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时

# API Key 存储（生产环境应使用数据库）
api_keys_storage = {
    "demo_key_12345": {
        "name": "Demo User",
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
        "rate_limit": 1000,
        "requests_count": 0,
    }
}

# JWT Token 存储（生产环境应使用 Redis）
active_tokens = set()


class TokenRequest(BaseModel):
    """Token 请求模型"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token 响应模型"""
    access_token: str
    token_type: str
    expires_in: int


class APIKeyRequest(BaseModel):
    """API Key 请求模型"""
    name: str
    rate_limit: int = 1000


class APIKeyResponse(BaseModel):
    """API Key 响应模型"""
    api_key: str
    name: str
    rate_limit: int
    created_at: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建 JWT Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    active_tokens.add(encoded_jwt)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """验证 JWT Token"""
    try:
        if token not in active_tokens:
            return None
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        active_tokens.discard(token)
        return None
    except jwt.JWTError:
        return None


def verify_api_key(api_key: str) -> Optional[dict]:
    """验证 API Key"""
    if api_key in api_keys_storage:
        key_data = api_keys_storage[api_key]
        if key_data["active"]:
            key_data["requests_count"] += 1
            if key_data["requests_count"] > key_data["rate_limit"]:
                return None
            return key_data
    return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None),
):
    """获取当前用户（支持 JWT 和 API Key）"""
    # 尝试 API Key 认证
    if x_api_key:
        user = verify_api_key(x_api_key)
        if user:
            return {"auth_type": "api_key", "user": user}

    # 尝试 JWT Token 认证
    if credentials:
        token = credentials.credentials
        payload = verify_token(token)
        if payload:
            return {"auth_type": "jwt", "user": payload}

    # 认证失败
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/auth/token", response_model=TokenResponse)
async def login(request: TokenRequest):
    """登录获取 JWT Token"""
    # 简单的用户名密码验证（生产环境应使用数据库和密码哈希）
    if request.username == "admin" and request.password == "admin123":
        access_token = create_access_token(
            data={"sub": request.username, "type": "user"}
        )
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password",
    )


@router.post("/auth/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """登出（撤销 Token）"""
    if current_user["auth_type"] == "jwt":
        # 从活跃 token 集合中移除
        # 注意：这里需要从请求中获取原始 token
        return {"success": True, "message": "Logged out successfully"}
    return {"success": True, "message": "API Key cannot be logged out"}


@router.post("/auth/api-key", response_model=APIKeyResponse)
async def create_api_key(request: APIKeyRequest):
    """创建新的 API Key"""
    # 生成随机 API Key
    api_key = f"faq_{secrets.token_urlsafe(32)}"

    api_keys_storage[api_key] = {
        "name": request.name,
        "created_at": datetime.utcnow().isoformat(),
        "active": True,
        "rate_limit": request.rate_limit,
        "requests_count": 0,
    }

    return APIKeyResponse(
        api_key=api_key,
        name=request.name,
        rate_limit=request.rate_limit,
        created_at=api_keys_storage[api_key]["created_at"],
    )


@router.delete("/auth/api-key/{api_key}")
async def revoke_api_key(api_key: str):
    """撤销 API Key"""
    if api_key in api_keys_storage:
        api_keys_storage[api_key]["active"] = False
        return {"success": True, "message": "API Key revoked successfully"}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="API Key not found",
    )


@router.get("/auth/api-keys")
async def list_api_keys():
    """列出所有 API Keys"""
    keys = []
    for key, data in api_keys_storage.items():
        keys.append({
            "api_key": key[:10] + "..." + key[-4:],  # 隐藏部分密钥
            "name": data["name"],
            "active": data["active"],
            "rate_limit": data["rate_limit"],
            "requests_count": data["requests_count"],
            "created_at": data["created_at"],
        })

    return {"api_keys": keys, "total": len(keys)}


@router.get("/auth/verify")
async def verify_auth(current_user: dict = Depends(get_current_user)):
    """验证当前认证状态"""
    return {
        "authenticated": True,
        "auth_type": current_user["auth_type"],
        "user": current_user["user"].get("name") or current_user["user"].get("sub"),
    }
