import os
import uuid
import logging
import time
from datetime import datetime
from celery import Celery
from config import Config
from services.database_service import DatabaseService
from .playlist_processor import PlaylistProcessor
from .single_video_processor import SingleVideoProcessor
from .batch_processor import BatchProcessor

logger = logging.getLogger(__name__)
celery = Celery(__name__, broker=Config.REDIS_URL, backend=Config.REDIS_URL)

def ensure_cookies_available():
    try:
        cookie_file = DatabaseService.get_cookie_file()
        if cookie_file:
            cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
            with open(cookies_path, 'wb') as f:
                f.write(cookie_file.content)
            logger.info(f"Arquivo de cookies disponibilizado para yt-dlp: {cookies_path}")
            return cookies_path
        return None
    except Exception as e:
        logger.error(f"Erro ao preparar arquivo de cookies: {e}")
        return None

@celery.task(bind=True)
def process_media(self, url, media_type, quality=None, bitrate=None):
    start_time = time.time()
    task_id = self.request.id
    
    try:
        logger.info(f"[{task_id}] Iniciando download: tipo={media_type}, url='{url}'")
        
        if not os.path.exists(Config.DOWNLOAD_FOLDER):
            os.makedirs(Config.DOWNLOAD_FOLDER)

        # Configurações base do yt-dlp
        ydl_opts = {
            'noplaylist': True,
            'quiet': True,
            'writeinfojson': False,
            'extract_flat': False,
            'ignoreerrors': True,
        }
        
        cookies_path = ensure_cookies_available()
        if cookies_path and os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            logger.info(f"[{task_id}] Usando arquivo de cookies")

        # Verifica se é playlist
        is_playlist = 'playlist' in url.lower() or 'list=' in url
        
        if is_playlist:
            processor = PlaylistProcessor(self, ydl_opts)
            return processor.process(url, media_type, quality, bitrate)
        else:
            processor = SingleVideoProcessor(self, ydl_opts)
            return processor.process(url, media_type, quality, bitrate)
        
    except Exception as e:
        logger.error(f"[{task_id}] Erro na tarefa: {e}", exc_info=True)
        self.update_state(
            state='FAILURE',
            meta={
                'stage': 'error',
                'message': f'Erro: {str(e)}',
                'progress': 0,
                'error': str(e)
            }
        )
        raise

@celery.task(bind=True)
def process_batch_download(self, urls, media_type, quality=None, bitrate=None, folder_id=None):
    """Processa download em lote de múltiplas URLs"""
    processor = BatchProcessor(self, ensure_cookies_available())
    return processor.process(urls, media_type, quality, bitrate, folder_id)