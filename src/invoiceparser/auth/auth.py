"""
Authentication utilities for password-based authentication
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import Config
from ..database import get_session
from ..database.models import User

logger = logging.getLogger(__name__)

# Password hashing
# Use bcrypt with specific configuration for compatibility
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
    bcrypt__ident="2b"
)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# JWT settings - will be loaded from config
_config: Config | None = None


def _get_config() -> Config:
    """Get config instance (lazy loading)"""
    global _config
    if _config is None:
        from ..core.config import Config
        _config = Config.load()
    return _config


def get_secret_key() -> str:
    """Get JWT secret key from config"""
    return _get_config().jwt_secret_key


def get_algorithm() -> str:
    """Get JWT algorithm from config"""
    return _get_config().jwt_algorithm


def get_access_token_expire_minutes() -> int:
    """Get access token expiration time from config"""
    return _get_config().jwt_access_token_expire_minutes


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Data to encode in token
        expires_delta: Token expiration time

    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=get_access_token_expire_minutes())

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_secret_key(), algorithm=get_algorithm())
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token to verify

    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[get_algorithm()])
        return payload
    except JWTError:
        return None


async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    """
    Get user by username

    Args:
        session: Database session
        username: Username

    Returns:
        User object or None
    """
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
    """
    Get user by ID

    Args:
        session: Database session
        user_id: User ID

    Returns:
        User object or None
    """
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> Optional[User]:
    """
    Authenticate a user by username and password

    Args:
        session: Database session
        username: Username
        password: Plain text password

    Returns:
        User object if authenticated, None otherwise
    """
    user = await get_user_by_username(session, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get current authenticated user from JWT token

    Args:
        token: JWT token from request

    Returns:
        Current user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(token)
        if payload is None:
            raise credentials_exception

        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # Get session from database
    async for session in get_session():
        user = await get_user_by_username(session, username)
        if user is None:
            raise credentials_exception

        # Update last login
        user.last_login = datetime.utcnow()
        await session.commit()

        return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user

    Args:
        current_user: Current user from get_current_user

    Returns:
        Active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

