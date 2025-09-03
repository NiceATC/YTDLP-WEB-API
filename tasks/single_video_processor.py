import os
import uuid
import logging
import time
from datetime import datetime
from yt_dlp import YoutubeDL
from config import Config
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

class SingleVideoProcessor:
    def __init__(self, task_self, base_opts):
        self.task_self = task_self
        self.base_opts = base_opts
        self.task_id = task_self.request.id

    def process(self, url, media_type, quality, bitrate):
        start_time = time.time()
        
        logger.info(f"[{self.task_id}] Processando vídeo único: {url}")
        
        # Atualiza status inicial
        self.task_self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'extracting',
                'message': 'Extraindo informações do vídeo...',
                'progress': 10,
                'type': 'single'
            }
        )
        
        # Nome único para o arquivo
        unique_filename = f"single_{self.task_id}_{uuid.uuid4().hex[:8]}"
        
        video_opts = self.base_opts.copy()
        video_opts['outtmpl'] = os.path.join(Config.DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s")

        if media_type == 'audio':
            video_opts['format'] = 'bestaudio/best'
            video_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': bitrate or '192'
            }]
            expected_extension = '.mp3'
        else:
            quality_filter = f"[height<={quality.replace('p', '')}]" if quality else ""
            video_opts['format'] = f'bestvideo{quality_filter}+bestaudio/best'
            video_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }]
            expected_extension = '.mp4'

        # Atualiza status
        self.task_self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'downloading',
                'message': 'Baixando vídeo...',
                'progress': 50,
                'type': 'single'
            }
        )

        with YoutubeDL(video_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

        # Atualiza status
        self.task_self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'processing',
                'message': 'Processando arquivo...',
                'progress': 80,
                'type': 'single'
            }
        )

        # Encontra e renomeia o arquivo baixado
        final_filename = f"{uuid.uuid4().hex}{expected_extension}"
        final_path = os.path.join(Config.DOWNLOAD_FOLDER, final_filename)
        
        # Procura pelo arquivo processado
        found_file = None
        for filename in os.listdir(Config.DOWNLOAD_FOLDER):
            if filename.startswith(unique_filename) and not filename.endswith('.json'):
                found_file = os.path.join(Config.DOWNLOAD_FOLDER, filename)
                break
        
        if found_file and os.path.exists(found_file):
            os.rename(found_file, final_path)
        else:
            raise FileNotFoundError(f"Arquivo processado não encontrado: {unique_filename}")

        file_size_mb = round(os.path.getsize(final_path) / (1024 * 1024), 2)
        DatabaseService.save_media_file(final_filename, info_dict, media_type, file_size_mb)

        processing_time = round(time.time() - start_time)
        
        upload_date_str = info_dict.get('upload_date')
        formatted_date = 'N/A'
        if upload_date_str:
            try:
                formatted_date = datetime.strptime(upload_date_str, '%Y%m%d').strftime('%d/%m/%Y')
            except ValueError:
                formatted_date = upload_date_str

        # Status final
        self.task_self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'message': 'Download concluído com sucesso!',
                'progress': 100,
                'type': 'single'
            }
        )

        return {
            'playlist': False,
            'download_url': f"{Config.BASE_URL}/api/download/{final_filename}",
            'title': info_dict.get('title', 'N/A'),
            'uploader': info_dict.get('uploader', 'N/A'),
            'thumbnail': info_dict.get('thumbnail', None),
            'duration_string': info_dict.get('duration_string', 'N/A'),
            'webpage_url': info_dict.get('webpage_url', '#'),
            'view_count': info_dict.get('view_count'),
            'like_count': info_dict.get('like_count'),
            'description': info_dict.get('description'),
            'upload_date': formatted_date,
            'time_spend': f"{processing_time}s",
        }