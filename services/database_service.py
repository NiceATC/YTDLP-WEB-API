import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from database.models import User, ApiKey, Settings, RequestHistory, MediaFile, CookieFile
from werkzeug.security import generate_password_hash, check_password_hash

class DatabaseService:
    
    @staticmethod
    def get_session() -> Session:
        return SessionLocal()
    
    # User Management
    @staticmethod
    def get_user() -> Optional[User]:
        """Retorna o usuário único do sistema"""
        with DatabaseService.get_session() as db:
            return db.query(User).first()
    
    @staticmethod
    def create_or_update_user(password: str) -> User:
        """Cria ou atualiza a senha do usuário"""
        with DatabaseService.get_session() as db:
            user = db.query(User).first()
            password_hash = generate_password_hash(password)
            
            if user:
                user.password_hash = password_hash
                user.updated_at = datetime.utcnow()
            else:
                user = User(password_hash=password_hash)
                db.add(user)
            
            db.commit()
            db.refresh(user)
            return user
    
    @staticmethod
    def verify_password(password: str) -> bool:
        """Verifica se a senha está correta"""
        user = DatabaseService.get_user()
        if not user:
            return False
        return check_password_hash(user.password_hash, password)
    
    # API Keys Management
    @staticmethod
    def get_api_keys() -> List[ApiKey]:
        """Retorna todas as chaves de API ativas"""
        with DatabaseService.get_session() as db:
            return db.query(ApiKey).filter(ApiKey.is_active == True).all()
    
    @staticmethod
    def create_api_key(name: str = None) -> ApiKey:
        """Cria uma nova chave de API"""
        with DatabaseService.get_session() as db:
            api_key = ApiKey(
                key=str(uuid.uuid4()),
                name=name or f"Chave {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            db.add(api_key)
            db.commit()
            db.refresh(api_key)
            return api_key
    
    @staticmethod
    def delete_api_key(key: str) -> bool:
        """Remove uma chave de API"""
        with DatabaseService.get_session() as db:
            api_key = db.query(ApiKey).filter(ApiKey.key == key).first()
            if api_key:
                api_key.is_active = False
                db.commit()
                return True
            return False
    
    @staticmethod
    def validate_api_key(key: str) -> bool:
        """Valida se uma chave de API é válida"""
        with DatabaseService.get_session() as db:
            api_key = db.query(ApiKey).filter(
                ApiKey.key == key, 
                ApiKey.is_active == True
            ).first()
            
            if api_key:
                # Atualiza último uso
                api_key.last_used = datetime.utcnow()
                db.commit()
                return True
            return False
    
    # Settings Management
    @staticmethod
    def get_setting(key: str, default: Any = None) -> Any:
        """Retorna uma configuração específica"""
        with DatabaseService.get_session() as db:
            setting = db.query(Settings).filter(Settings.key == key).first()
            if setting:
                try:
                    return json.loads(setting.value)
                except:
                    return setting.value
            return default
    
    @staticmethod
    def set_setting(key: str, value: Any) -> None:
        """Define uma configuração"""
        with DatabaseService.get_session() as db:
            setting = db.query(Settings).filter(Settings.key == key).first()
            value_str = json.dumps(value) if not isinstance(value, str) else value
            
            if setting:
                setting.value = value_str
                setting.updated_at = datetime.utcnow()
            else:
                setting = Settings(key=key, value=value_str)
                db.add(setting)
            
            db.commit()
    
    @staticmethod
    def get_all_settings() -> Dict[str, Any]:
        """Retorna todas as configurações"""
        with DatabaseService.get_session() as db:
            settings = db.query(Settings).all()
            result = {}
            for setting in settings:
                try:
                    result[setting.key] = json.loads(setting.value)
                except:
                    result[setting.key] = setting.value
            return result
    
    # Request History
    @staticmethod
    def log_request(api_key: str, request_data: Dict, response_data: Dict, status: str) -> None:
        """Registra uma requisição no histórico"""
        with DatabaseService.get_session() as db:
            history = RequestHistory(
                api_key_used=f"{api_key[:4]}...{api_key[-4:]}",
                request_data=request_data,
                response_data=response_data,
                status=status
            )
            db.add(history)
            db.commit()
    
    @staticmethod
    def get_request_history(limit: int = 100) -> List[RequestHistory]:
        """Retorna o histórico de requisições"""
        with DatabaseService.get_session() as db:
            return db.query(RequestHistory).order_by(
                RequestHistory.created_at.desc()
            ).limit(limit).all()
    
    # Media Files
    @staticmethod
    def save_media_file(filename: str, metadata: Dict, media_type: str, file_size_mb: float) -> MediaFile:
        """Salva informações de um arquivo de mídia"""
        with DatabaseService.get_session() as db:
            media_file = MediaFile(
                filename=filename,
                original_url=metadata.get('webpage_url', ''),
                title=metadata.get('title', 'N/A'),
                uploader=metadata.get('uploader', 'N/A'),
                duration_string=metadata.get('duration_string', 'N/A'),
                view_count=metadata.get('view_count', 0),
                like_count=metadata.get('like_count', 0),
                upload_date=metadata.get('upload_date', 'N/A'),
                description=metadata.get('description', ''),
                thumbnail_url=metadata.get('thumbnail', ''),
                file_size_mb=int(file_size_mb),
                media_type=media_type
            )
            db.add(media_file)
            db.commit()
            db.refresh(media_file)
            return media_file
    
    @staticmethod
    def get_media_files() -> List[MediaFile]:
        """Retorna todos os arquivos de mídia"""
        with DatabaseService.get_session() as db:
            return db.query(MediaFile).order_by(MediaFile.created_at.desc()).all()
    
    @staticmethod
    def delete_media_file(filename: str) -> bool:
        """Remove um arquivo de mídia do banco"""
        with DatabaseService.get_session() as db:
            media_file = db.query(MediaFile).filter(MediaFile.filename == filename).first()
            if media_file:
                db.delete(media_file)
                db.commit()
                return True
            return False
    
    # Cookie Management
    @staticmethod
    def save_cookie_file(content: bytes, filename: str = 'cookies.txt') -> CookieFile:
        """Salva o arquivo de cookies"""
        with DatabaseService.get_session() as db:
            # Remove cookie anterior se existir
            old_cookie = db.query(CookieFile).first()
            if old_cookie:
                db.delete(old_cookie)
            
            cookie_file = CookieFile(content=content, filename=filename)
            db.add(cookie_file)
            db.commit()
            db.refresh(cookie_file)
            return cookie_file
    
    @staticmethod
    def get_cookie_file() -> Optional[CookieFile]:
        """Retorna o arquivo de cookies atual"""
        with DatabaseService.get_session() as db:
            return db.query(CookieFile).first()
    
    @staticmethod
    def delete_cookie_file() -> bool:
        """Remove o arquivo de cookies"""
        with DatabaseService.get_session() as db:
            cookie_file = db.query(CookieFile).first()
            if cookie_file:
                db.delete(cookie_file)
                db.commit()
                return True
            return False