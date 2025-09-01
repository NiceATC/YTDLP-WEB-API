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
            logger.info(f"Tarefa {self.request.id}: Usando arquivo de cookies: {cookies_path}")

        # Verifica se é playlist
        is_playlist = 'playlist' in url.lower() or 'list=' in url
        
        if is_playlist:
            logger.info(f"Tarefa {self.request.id}: Detectada playlist, processando...")
            ydl_opts['noplaylist'] = False
            ydl_opts['playlistend'] = 50
            
            # Primeiro, extrai informações da playlist
            with YoutubeDL({'extract_flat': True, 'quiet': True}) as ydl:
                playlist_info = ydl.extract_info(url, download=False)
            
            if 'entries' in playlist_info:
                entries = [entry for entry in playlist_info['entries'] if entry is not None]
                logger.info(f"Tarefa {self.request.id}: Playlist com {len(entries)} vídeos encontrada")
                
                results = []
                total_videos = len(entries)
                
                for i, entry in enumerate(entries):
                    try:
                        # Atualiza progresso
                        progress = int((i / total_videos) * 100)
                        self.update_state(
                            state='PROGRESS',
                            meta={
                                'current': i + 1,
                                'total': total_videos,
                                'progress': progress,
                                'status': f'Processando vídeo {i + 1}/{total_videos}: {entry.get("title", "N/A")}'
                            }
                        )
                        
                        video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                        logger.info(f"Tarefa {self.request.id}: Processando vídeo {i+1}/{total_videos}: {video_url}")
                        
                        # Configurações específicas para este vídeo
                        video_opts = ydl_opts.copy()
                        video_opts['noplaylist'] = True
                        
                        # Nome único para cada arquivo
                        video_filename = f"{uuid.uuid4()}"
                        video_opts['outtmpl'] = os.path.join(Config.DOWNLOAD_FOLDER, f"{video_filename}.%(ext)s")
                        
                        if is_audio:
                            video_opts['format'] = 'bestaudio/best'
                            video_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': bitrate or '192'}]
                            final_extension = '.mp3'
                        else:
                            quality_filter = f"[height<={quality.replace('p', '')}]" if quality else ""
                            video_opts['format'] = f'bestvideo{quality_filter}+bestaudio/best'
                            video_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
                            final_extension = '.mp4'
                        
                        # Download do vídeo individual
                        with YoutubeDL(video_opts) as ydl:
                            video_info = ydl.extract_info(video_url, download=True)
                        
                        # Encontra o arquivo baixado
                        final_filename = f"{uuid.uuid4()}{final_extension}"
                        final_path = os.path.join(Config.DOWNLOAD_FOLDER, final_filename)
                        
                        # Procura pelo arquivo processado
                        found_file = None
                        for f in os.listdir(Config.DOWNLOAD_FOLDER):
                            if f.startswith(video_filename) and not f.endswith('.json'):
                                found_file = os.path.join(Config.DOWNLOAD_FOLDER, f)
                                break
                        
                        if found_file and os.path.exists(found_file):
                            os.rename(found_file, final_path)
                            
                            # Salva no banco de dados
                            file_size_mb = round(os.path.getsize(final_path) / (1024 * 1024), 2)
                            DatabaseService.save_media_file(final_filename, video_info, media_type, file_size_mb)
                            
                            results.append({
                                'filename': final_filename,
                                'title': video_info.get('title', f'Vídeo {i+1}'),
                                'download_url': f"{Config.BASE_URL}/api/download/{final_filename}"
                            })
                            
                            logger.info(f"Tarefa {self.request.id}: Vídeo {i+1}/{total_videos} processado com sucesso")
                        else:
                            logger.warning(f"Tarefa {self.request.id}: Arquivo não encontrado para vídeo {i+1}")
                            
                    except Exception as e:
                        logger.error(f"Tarefa {self.request.id}: Erro ao processar vídeo {i+1}: {e}")
                        continue
                
                if not results:
                    raise Exception("Nenhum vídeo da playlist pôde ser processado")
                
                processing_time = round(time.time() - start_time)
                
                return {
                    'playlist': True,
                    'playlist_title': playlist_info.get('title', 'Playlist'),
                    'playlist_count': len(results),
                    'videos': results,
                    'time_spend': f"{processing_time}s",
                    'download_url': results[0]['download_url'] if results else None,
                    'title': f"{playlist_info.get('title', 'Playlist')} ({len(results)} vídeos)",
                    'uploader': playlist_info.get('uploader', 'N/A'),
                    'thumbnail': playlist_info.get('thumbnail', None),
                    'duration_string': f"{len(results)} vídeos",
                    'webpage_url': url,
                    'view_count': None,
                    'like_count': None,
                    'description': f"Playlist com {len(results)} vídeos baixados",
                    'upload_date': 'N/A'
                }
        
        # Processamento de vídeo único
        temp_base_path = os.path.join(Config.DOWNLOAD_FOLDER, self.request.id)
        ydl_opts['outtmpl'] = f"{temp_base_path}.%(ext)s"

        if is_audio:
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': bitrate or '192'}]
            final_extension = '.mp3'
        else:
            quality_filter = f"[height<={quality.replace('p', '')}]" if quality else ""
            ydl_opts['format'] = f'bestvideo{quality_filter}+bestaudio/best'
            ydl_opts['postprocessors'] = [{'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}]
            final_extension = '.mp4'

        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

        processed_filepath = f"{temp_base_path}{final_extension}"
        output_filename = f"{uuid.uuid4()}{final_extension}"
        output_path = os.path.join(Config.DOWNLOAD_FOLDER, output_filename)

        if os.path.exists(processed_filepath):
            os.rename(processed_filepath, output_path)
        else:
            found = False
            for f in os.listdir(Config.DOWNLOAD_FOLDER):
                if f.startswith(self.request.id) and not f.endswith('.json'):
                    os.rename(os.path.join(Config.DOWNLOAD_FOLDER, f), output_path)
                    found = True
                    break
            if not found:
                raise FileNotFoundError(f"O ficheiro processado '{processed_filepath}' não foi encontrado após o download.")

        file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
        DatabaseService.save_media_file(output_filename, info_dict, media_type, file_size_mb)

        processing_time = round(time.time() - start_time)
        
        upload_date_str = info_dict.get('upload_date')
        formatted_date = 'N/A'
        if upload_date_str:
            try:
                formatted_date = datetime.strptime(upload_date_str, '%Y%m%d').strftime('%d/%m/%Y')
            except ValueError:
                formatted_date = upload_date_str

        return {
            'playlist': False,
            'download_url': f"{Config.BASE_URL}/api/download/{output_filename}",
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
        
    except Exception as e:
        logger.error(f"Erro na tarefa {self.request.id}: {e}", exc_info=True)
        raise

@celery.task(bind=True)
def process_batch_download(self, batch_id, urls, media_type, quality=None, bitrate=None, folder_id=None):
    """Processa download em lote"""
    try:
        logger.info(f"Iniciando batch download {batch_id} com {len(urls)} URLs")
        
        total_urls = len(urls)
        completed = 0
        failed = 0
        results = []
        
        for i, url in enumerate(urls):
            try:
                # Atualiza progresso
                progress = int((i / total_urls) * 100)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i + 1,
                        'total': total_urls,
                        'progress': progress,
                        'completed': completed,
                        'failed': failed,
                        'status': f'Processando URL {i + 1}/{total_urls}'
                    }
                )
                
                # Processa cada URL individualmente
                task = process_media.delay(url, media_type, quality, bitrate)
                result = task.get(timeout=300)  # 5 minutos timeout por vídeo
                
                if result:
                    completed += 1
                    results.append({
                        'url': url,
                        'status': 'success',
                        'result': result
                    })
                    
                    # Se especificou pasta, move o arquivo
                    if folder_id and result.get('filename'):
                        DatabaseService.move_file_to_folder_by_filename(result['filename'], folder_id)
                else:
                    failed += 1
                    results.append({
                        'url': url,
                        'status': 'failed',
                        'error': 'Resultado vazio'
                    })
                
            except Exception as e:
                failed += 1
                logger.error(f"Erro ao processar URL {url}: {e}")
                results.append({
                    'url': url,
                    'status': 'failed',
                    'error': str(e)
                })
            
            # Atualiza progresso no banco
            DatabaseService.update_batch_progress(batch_id, completed, failed)
        
        # Finaliza batch
        DatabaseService.complete_batch_download(batch_id)
        
        return {
            'batch_id': batch_id,
            'total': total_urls,
            'completed': completed,
            'failed': failed,
            'results': results
        }
        
    except Exception as e:
        logger.error(f"Erro no batch download {batch_id}: {e}")
        DatabaseService.fail_batch_download(batch_id, str(e))
        raise