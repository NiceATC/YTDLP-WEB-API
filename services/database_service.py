import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from database import get_db, SessionLocal
from database.models import User, ApiKey, Settings, RequestHistory, MediaFile, CookieFile, AppSettings, Folder, BatchDownload
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
    
    @staticmethod
    def delete_history_item(history_id: int) -> bool:
        """Remove um item específico do histórico"""
        with DatabaseService.get_session() as db:
            history_item = db.query(RequestHistory).filter(RequestHistory.id == history_id).first()
            if history_item:
                db.delete(history_item)
                db.commit()
                return True
            return False
    
    @staticmethod
    def clear_history() -> None:
        """Limpa todo o histórico de requisições"""
        with DatabaseService.get_session() as db:
            db.query(RequestHistory).delete()
            db.commit()
    
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
    def get_media_files(folder_id: int = None, search: str = None, media_type: str = None, sort_by: str = 'created_at', sort_order: str = 'desc', limit: int = None, offset: int = 0) -> List[MediaFile]:
        """Retorna todos os arquivos de mídia"""
        with DatabaseService.get_session() as db:
            query = db.query(MediaFile)
            
            # Filter by folder
            if folder_id is not None:
                if folder_id == 0:  # Root folder
                    query = query.filter(MediaFile.folder_id.is_(None))
                else:
                query = query.filter(MediaFile.folder_id == folder_id)
            
            # Search filter
            if search:
                query = query.filter(
                    MediaFile.title.ilike(f'%{search}%') |
                    MediaFile.uploader.ilike(f'%{search}%')
                )
            
            # Media type filter
            if media_type:
                query = query.filter(MediaFile.media_type == media_type)
            
            # Sorting
            if sort_order == 'desc':
                query = query.order_by(getattr(MediaFile, sort_by).desc())
            else:
                query = query.order_by(getattr(MediaFile, sort_by))
            
            # Pagination
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    @staticmethod
    def get_media_files_count(folder_id: int = None, search: str = None, media_type: str = None) -> int:
        """Retorna o total de arquivos com filtros"""
        with DatabaseService.get_session() as db:
            query = db.query(MediaFile)
            
            if folder_id is not None:
                if folder_id == 0:  # Root folder
                    query = query.filter(MediaFile.folder_id.is_(None))
                else:
                query = query.filter(MediaFile.folder_id == folder_id)
            if search:
                query = query.filter(
                    MediaFile.title.ilike(f'%{search}%') |
                    MediaFile.uploader.ilike(f'%{search}%')
                )
            if media_type:
                query = query.filter(MediaFile.media_type == media_type)
            
            return query.count()
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
    
    @staticmethod
    def move_file_to_folder(file_id: int, folder_id: int = None) -> bool:
        """Move um arquivo para uma pasta"""
        with DatabaseService.get_session() as db:
            media_file = db.query(MediaFile).filter(MediaFile.id == file_id).first()
            if media_file:
                media_file.folder_id = folder_id
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
    
    # App Settings Management
    @staticmethod
    def get_app_settings() -> Optional[AppSettings]:
        """Retorna as configurações da aplicação"""
        with DatabaseService.get_session() as db:
            return db.query(AppSettings).first()
    
    @staticmethod
    def update_app_settings(**kwargs) -> AppSettings:
        """Atualiza as configurações da aplicação"""
        with DatabaseService.get_session() as db:
            settings = db.query(AppSettings).first()
            if not settings:
                settings = AppSettings()
                db.add(settings)
            
            for key, value in kwargs.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            settings.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(settings)
            return settings
    
    # Folder Management
    @staticmethod
    def get_folders() -> List[Folder]:
        """Retorna todas as pastas"""
        with DatabaseService.get_session() as db:
            return db.query(Folder).order_by(Folder.name).all()
    
    @staticmethod
    def create_folder(name: str, parent_id: int = None) -> Folder:
        """Cria uma nova pasta"""
        with DatabaseService.get_session() as db:
            folder = Folder(name=name, parent_id=parent_id)
            db.add(folder)
            db.commit()
            db.refresh(folder)
            return folder
    
    @staticmethod
    def delete_folder(folder_id: int) -> bool:
        """Remove uma pasta"""
        with DatabaseService.get_session() as db:
            folder = db.query(Folder).filter(Folder.id == folder_id).first()
            if folder:
                # Move files to root
                db.query(MediaFile).filter(MediaFile.folder_id == folder_id).update({'folder_id': None})
                db.delete(folder)
                db.commit()
                return True
            return False
    
    # Batch Download Management
    @staticmethod
    def create_batch_download(name: str, urls: List[str], media_type: str, **kwargs) -> BatchDownload:
        """Cria um download em lote"""
        with DatabaseService.get_session() as db:
            batch = BatchDownload(
                name=name,
                urls=urls,
                media_type=media_type,
                total_files=len(urls),
                **kwargs
            )
            db.add(batch)
            db.commit()
            db.refresh(batch)
            return batch
    
    @staticmethod
    def get_batch_downloads() -> List[BatchDownload]:
        """Retorna todos os downloads em lote"""
        with DatabaseService.get_session() as db:
            return db.query(BatchDownload).order_by(BatchDownload.created_at.desc()).all()
    
    @staticmethod
    def update_batch_progress(batch_id: int, completed: int, failed: int = 0) -> None:
        """Atualiza o progresso de um download em lote"""
        with DatabaseService.get_session() as db:
            batch = db.query(BatchDownload).filter(BatchDownload.id == batch_id).first()
            if batch:
                batch.completed_files = completed
                batch.failed_files = failed
                batch.progress = int((completed + failed) / batch.total_files * 100)
                
                if batch.progress >= 100:
                    batch.status = 'completed'
                    batch.completed_at = datetime.utcnow()
                elif failed > 0:
                    batch.status = 'processing'
                
                db.commit()