from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, EmailStr

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    CURATOR = "curator"

class UserProfile(BaseModel):
    """
    Representa o perfil público/privado do usuário no sistema.
    Átomo fundamental para controle de acesso.
    """
    id: str = Field(..., description="UUID do usuário no Supabase")
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    created_at: datetime
    last_login: Optional[datetime] = None
    credits: int = 0
    
    class Config:
        from_attributes = True

class AuthSession(BaseModel):
    """
    Representa a sessão ativa localmente.
    Nunca deve ser salva em disco sem criptografia.
    """
    access_token: str
    refresh_token: str
    expires_at: int
    user: UserProfile
