import os
import uuid
import logging
import json
from celery import Celery
from yt_dlp import YoutubeDL
from config import Config

logger = logging.getLogger(__name__)
celery = Celery(__name__, broker=Config.REDIS_URL, backend=Config.REDIS_URL)

@celery.task(bind=True)
def process_media(self, search_query, media_type, quality=None, bitrate=None):
    try:
        logger.info(f"Iniciando tarefa {self.request.id}: tipo={media_type}, query='{search_query}'")
        
        if not os.path.exists(Config.DOWNLOAD_FOLDER):
            os.makedirs(Config.DOWNLOAD_FOLDER)

        is_audio = media_type == 'audio'
        temp_base_path = os.path.join(Config.DOWNLOAD_FOLDER, self.request.id)

        ydl_opts = {
            'outtmpl': f"{temp_base_path}.%(ext)s",
            'noplaylist': True,
            'quiet': True,
            'writeinfojson': True,
        }
        
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'

        if is_audio:
            logger.info(f"Tarefa {self.request.id}: Configurando para download e conversao de audio para MP3.")
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': bitrate or '192'}]
            final_extension = '.mp3'
        else:
            logger.info(f"Tarefa {self.request.id}: Configurando para download de video para MP4.")
            quality_filter = f"[height<={quality.replace('p', '')}]" if quality else ""
            ydl_opts['format'] = f'bestvideo{quality_filter}+bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
            final_extension = '.mp4'

        logger.info(f"Tarefa {self.request.id}: Iniciando download e processamento com yt-dlp...")
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(search_query, download=True)
        logger.info(f"Tarefa {self.request.id}: Processamento do yt-dlp concluido.")

        final_info = info_dict['entries'][0] if 'entries' in info_dict else info_dict

        processed_filepath = f"{temp_base_path}{final_extension}"
        output_filename = f"{uuid.uuid4()}{final_extension}"
        output_path = os.path.join(Config.DOWNLOAD_FOLDER, output_filename)

        if os.path.exists(processed_filepath):
            os.rename(processed_filepath, output_path)
            logger.info(f"Tarefa {self.request.id}: Ficheiro final renomeado para {output_path}")
        else:
            found = False
            for f in os.listdir(Config.DOWNLOAD_FOLDER):
                if f.startswith(self.request.id) and not f.endswith('.json'):
                    os.rename(os.path.join(Config.DOWNLOAD_FOLDER, f), output_path)
                    logger.info(f"Tarefa {self.request.id}: Ficheiro encontrado e renomeado para {output_path}")
                    found = True
                    break
            if not found:
                logger.error(f"Tarefa {self.request.id}: ERRO CRITICO! O ficheiro processado '{processed_filepath}' nao foi encontrado.")
                raise FileNotFoundError(f"O ficheiro processado '{processed_filepath}' nao foi encontrado apos o download.")

        temp_info_path = f"{temp_base_path}.info.json"
        if os.path.exists(temp_info_path):
            final_info_path = f"{output_path}.info.json"
            os.rename(temp_info_path, final_info_path)
            logger.info(f"Tarefa {self.request.id}: Ficheiro de metadados salvo em {final_info_path}")

        download_url = f"{Config.BASE_URL}/api/download/{output_filename}"
        logger.info(f"Tarefa {self.request.id}: Concluida com sucesso.")
        
        return {
            'download_url': download_url,
            'title': final_info.get('title', 'N/A'),
            'uploader': final_info.get('uploader', 'N/A'),
            'thumbnail': final_info.get('thumbnail', None),
            'duration_string': final_info.get('duration_string', 'N/A'),
            'webpage_url': final_info.get('webpage_url', '#'),
            'view_count': final_info.get('view_count'),
            'like_count': final_info.get('like_count'),
            'description': final_info.get('description'),
            'upload_date': final_info.get('upload_date'),
        }
    except Exception as e:
        logger.error(f"Erro na tarefa {self.request.id}: {e}", exc_info=True)
        raise
