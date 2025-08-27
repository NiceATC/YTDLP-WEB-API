import os
import uuid
import logging
import json
import time
from datetime import datetime
from celery import Celery
from yt_dlp import YoutubeDL
from config import Config
from services.database_service import DatabaseService

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
    try:
        logger.info(f"Iniciando tarefa {self.request.id}: tipo={media_type}, url='{url}'")
        
        if not os.path.exists(Config.DOWNLOAD_FOLDER):
            os.makedirs(Config.DOWNLOAD_FOLDER)

        is_audio = media_type == 'audio'
        temp_base_path = os.path.join(Config.DOWNLOAD_FOLDER, self.request.id)

        ydl_opts = {
            'outtmpl': f"{temp_base_path}.%(ext)s",
            'noplaylist': True,
            'quiet': True,
            'writeinfojson': True,
            'extract_flat': False,
            'ignoreerrors': True,
        }
        
        cookies_path = ensure_cookies_available()
        if cookies_path and os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            logger.info(f"Tarefa {self.request.id}: Usando arquivo de cookies: {cookies_path}")
        else:
            logger.warning(f"Tarefa {self.request.id}: Nenhum arquivo de cookies disponível")

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
        logger.info(f"Tarefa {self.request.id}: Opções do yt-dlp: {json.dumps(ydl_opts, indent=2)}")
        
        # Handle playlist URLs
        if 'playlist' in url.lower() or 'list=' in url:
            logger.info(f"Tarefa {self.request.id}: Detectada playlist, processando individualmente...")
            ydl_opts['noplaylist'] = False
            ydl_opts['playlistend'] = 50  # Máximo 50 vídeos
            ydl_opts['extract_flat'] = False  # Força extração completa
        
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
        # Processa resultados de playlist
        if 'entries' in info_dict:
            entries = [entry for entry in info_dict['entries'] if entry is not None]
            logger.info(f"Tarefa {self.request.id}: Playlist com {len(entries)} itens válidos processada")
            
            if not entries:
                raise Exception("Nenhum vídeo válido encontrado na playlist")
            
            # Processa cada vídeo da playlist
            results = []
            for i, entry in enumerate(entries):
                try:
                    # Cria nome único para cada arquivo
                    entry_filename = f"{uuid.uuid4()}{final_extension}"
                    entry_output_path = os.path.join(Config.DOWNLOAD_FOLDER, entry_filename)
                    
                    # Encontra o arquivo processado para este vídeo
                    entry_temp_path = None
                    for f in os.listdir(Config.DOWNLOAD_FOLDER):
                        if f.startswith(self.request.id) and not f.endswith('.json') and f not in [r['filename'] for r in results]:
                            entry_temp_path = os.path.join(Config.DOWNLOAD_FOLDER, f)
                            break
                    
                    if entry_temp_path and os.path.exists(entry_temp_path):
                        os.rename(entry_temp_path, entry_output_path)
                        
                        # Salva no banco de dados
                        file_size_mb = round(os.path.getsize(entry_output_path) / (1024 * 1024), 2)
                        DatabaseService.save_media_file(entry_filename, entry, media_type, file_size_mb)
                        
                        results.append({
                            'filename': entry_filename,
                            'title': entry.get('title', f'Vídeo {i+1}'),
                            'download_url': f"{Config.BASE_URL}/api/download/{entry_filename}"
                        })
                        
                        logger.info(f"Tarefa {self.request.id}: Vídeo {i+1}/{len(entries)} processado: {entry.get('title', 'N/A')}")
                    
                except Exception as e:
                    logger.error(f"Tarefa {self.request.id}: Erro ao processar vídeo {i+1}: {e}")
                    continue
            
            if not results:
                raise Exception("Nenhum vídeo da playlist pôde ser processado")
            
            # Retorna informações do primeiro vídeo como principal, mas inclui todos os resultados
            final_info = entries[0]
            playlist_info = {
                'playlist_title': info_dict.get('title', 'Playlist'),
                'playlist_count': len(results),
                'videos': results
            }
        else:
            final_info = info_dict
            playlist_info = None

        logger.info(f"Tarefa {self.request.id}: Processamento do yt-dlp concluido.")

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

        file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
        DatabaseService.save_media_file(output_filename, final_info, media_type, file_size_mb)

        temp_info_path = f"{temp_base_path}.info.json"
        if os.path.exists(temp_info_path):
            os.remove(temp_info_path)

        download_url = f"{Config.BASE_URL}/api/download/{output_filename}"
        logger.info(f"Tarefa {self.request.id}: Concluida com sucesso.")
        
        processing_time = round(time.time() - start_time)
        
        upload_date_str = final_info.get('upload_date')
        formatted_date = 'N/A'
        if upload_date_str:
            try:
                formatted_date = datetime.strptime(upload_date_str, '%Y%m%d').strftime('%d/%m/%Y')
            except ValueError:
                logger.warning(f"Tarefa {self.request.id}: Formato de data inválido '{upload_date_str}'")
                formatted_date = upload_date_str

        result = {
            'download_url': download_url,
            'title': final_info.get('title', 'N/A'),
            'uploader': final_info.get('uploader', 'N/A'),
            'thumbnail': final_info.get('thumbnail', None),
            'duration_string': final_info.get('duration_string', 'N/A'),
            'webpage_url': final_info.get('webpage_url', '#'),
            'view_count': final_info.get('view_count'),
            'like_count': final_info.get('like_count'),
            'description': final_info.get('description'),
            'upload_date': formatted_date,
            'time_spend': f"{processing_time}s",
        }
        
        # Adiciona informações de playlist se aplicável
        if playlist_info:
            result['playlist'] = playlist_info
            result['title'] = f"{playlist_info['playlist_title']} ({playlist_info['playlist_count']} vídeos)"
        
        return result
    except Exception as e:
        logger.error(f"Erro na tarefa {self.request.id}: {e}", exc_info=True)
        raise
