from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class ApiKey(Base):
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_used = Column(DateTime, nullable=True)

class Settings(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class RequestHistory(Base):
    __tablename__ = 'request_history'
    
    id = Column(Integer, primary_key=True)
    api_key_used = Column(String(50), nullable=False)
    request_data = Column(JSON, nullable=False)
    response_data = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=func.now())

class MediaFile(Base):
    __tablename__ = 'media_files'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(255), unique=True, nullable=False)
    original_url = Column(Text, nullable=False)
    title = Column(String(500), nullable=True)
    uploader = Column(String(200), nullable=True)
    duration_string = Column(String(20), nullable=True)
    view_count = Column(Integer, nullable=True)
    like_count = Column(Integer, nullable=True)
    upload_date = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    file_size_mb = Column(Integer, nullable=True)
    media_type = Column(String(10), nullable=False)  # 'audio' or 'video'
    created_at = Column(DateTime, default=func.now())

class CookieFile(Base):
    __tablename__ = 'cookie_files'
    
    id = Column(Integer, primary_key=True)
    content = Column(LargeBinary, nullable=False)
    filename = Column(String(100), default='cookies.txt')
    uploaded_at = Column(DateTime, default=func.now())