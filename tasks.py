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
    task_id = self.request.id
    
    try:
        logger.info(f"[{task_id}] Iniciando download: tipo={media_type}, url='{url}'")
        
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
            logger.info(f"[{task_id}] Usando arquivo de cookies")

        # Verifica se é playlist
        is_playlist = 'playlist' in url.lower() or 'list=' in url
        
        if is_playlist:
            return process_playlist(self, url, media_type, quality, bitrate, ydl_opts)
        else:
            return process_single_video(self, url, media_type, quality, bitrate, ydl_opts)
        
    except Exception as e:
        logger.error(f"[{task_id}] Erro na tarefa: {e}", exc_info=True)
        raise

def process_playlist(task_self, url, media_type, quality, bitrate, base_opts):
    task_id = task_self.request.id
    start_time = time.time()
    
    logger.info(f"[{task_id}] Processando playlist: {url}")
    
    # Atualiza status inicial
    task_self.update_state(
        state='PROGRESS',
        meta={
            'stage': 'extracting',
            'message': 'Extraindo informações da playlist...',
            'progress': 5
        }
    )
    
    # Extrai informações da playlist
    extract_opts = base_opts.copy()
    extract_opts.update({
        'extract_flat': True,
        'noplaylist': False,
        'playlistend': 50
    })
    
    with YoutubeDL(extract_opts) as ydl:
        playlist_info = ydl.extract_info(url, download=False)
    
    if 'entries' not in playlist_info:
        raise Exception("Playlist não encontrada ou vazia")
    
    entries = [entry for entry in playlist_info['entries'] if entry is not None]
    total_videos = len(entries)
    
    logger.info(f"[{task_id}] Playlist com {total_videos} vídeos encontrada")
    
    # Atualiza status
    task_self.update_state(
        state='PROGRESS',
        meta={
            'stage': 'downloading',
            'message': f'Baixando {total_videos} vídeos...',
            'progress': 10,
            'total_videos': total_videos,
            'completed_videos': 0,
            'failed_videos': 0
        }
    )
    
    results = []
    completed = 0
    failed = 0
    
    for i, entry in enumerate(entries):
        try:
            # Calcula progresso (10% para extração + 90% para downloads)
            download_progress = int(10 + (i / total_videos) * 90)
            
            video_title = entry.get('title', f'Vídeo {i+1}')
            logger.info(f"[{task_id}] Processando vídeo {i+1}/{total_videos}: {video_title}")
            
            # Atualiza status
            task_self.update_state(
                state='PROGRESS',
                meta={
                    'stage': 'downloading',
                    'message': f'Baixando: {video_title}',
                    'progress': download_progress,
                    'total_videos': total_videos,
                    'completed_videos': completed,
                    'failed_videos': failed,
                    'current_video': i + 1,
                    'current_title': video_title
                }
            )
            
            # URL do vídeo individual
            video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
            
            # Nome único para cada arquivo
            unique_filename = f"playlist_{task_id}_{i}_{uuid.uuid4().hex[:8]}"
            
            # Configurações para este vídeo específico
            video_opts = base_opts.copy()
            video_opts.update({
                'noplaylist': True,
                'outtmpl': os.path.join(Config.DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s")
            })
            
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
            
            # Download do vídeo
            with YoutubeDL(video_opts) as ydl:
                video_info = ydl.extract_info(video_url, download=True)
            
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
                # Renomeia para nome final
                os.rename(found_file, final_path)
                
                # Salva no banco de dados
                file_size_mb = round(os.path.getsize(final_path) / (1024 * 1024), 2)
                DatabaseService.save_media_file(final_filename, video_info, media_type, file_size_mb)
                
                results.append({
                    'filename': final_filename,
                    'title': video_info.get('title', video_title),
                    'download_url': f"{Config.BASE_URL}/api/download/{final_filename}",
                    'duration': video_info.get('duration_string', 'N/A'),
                    'uploader': video_info.get('uploader', 'N/A')
                })
                
                completed += 1
                logger.info(f"[{task_id}] Vídeo {i+1}/{total_videos} concluído: {final_filename}")
            else:
                failed += 1
                logger.warning(f"[{task_id}] Arquivo não encontrado para vídeo {i+1}: {video_title}")
                
        except Exception as e:
            failed += 1
            logger.error(f"[{task_id}] Erro ao processar vídeo {i+1}: {e}")
            continue
    
    if not results:
        raise Exception("Nenhum vídeo da playlist pôde ser processado")
    
    processing_time = round(time.time() - start_time)
    
    # Status final
    task_self.update_state(
        state='SUCCESS',
        meta={
            'stage': 'completed',
            'message': f'Playlist concluída: {completed} sucessos, {failed} falhas',
            'progress': 100,
            'total_videos': total_videos,
            'completed_videos': completed,
            'failed_videos': failed
        }
    )
    
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
        'description': f"Playlist com {len(results)} vídeos baixados com sucesso",
        'upload_date': 'N/A'
    }

def process_single_video(task_self, url, media_type, quality, bitrate, base_opts):
    task_id = task_self.request.id
    start_time = time.time()
    
    logger.info(f"[{task_id}] Processando vídeo único: {url}")
    
    # Atualiza status inicial
    task_self.update_state(
        state='PROGRESS',
        meta={
            'stage': 'extracting',
            'message': 'Extraindo informações do vídeo...',
            'progress': 10
        }
    )
    
    # Nome único para o arquivo
    unique_filename = f"single_{task_id}_{uuid.uuid4().hex[:8]}"
    
    video_opts = base_opts.copy()
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
    task_self.update_state(
        state='PROGRESS',
        meta={
            'stage': 'downloading',
            'message': 'Baixando vídeo...',
            'progress': 50
        }
    )

    with YoutubeDL(video_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)

    # Atualiza status
    task_self.update_state(
        state='PROGRESS',
        meta={
            'stage': 'processing',
            'message': 'Processando arquivo...',
            'progress': 80
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
    task_self.update_state(
        state='SUCCESS',
        meta={
            'stage': 'completed',
            'message': 'Download concluído com sucesso!',
            'progress': 100
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

@celery.task(bind=True)
def process_batch_download(self, urls, media_type, quality=None, bitrate=None, folder_id=None):
    """Processa download em lote de múltiplas URLs"""
    task_id = self.request.id
    start_time = time.time()
    
    try:
        logger.info(f"[{task_id}] Iniciando batch download com {len(urls)} URLs")
        
        total_urls = len(urls)
        completed = 0
        failed = 0
        results = []
        
        # Status inicial
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'batch_processing',
                'message': f'Iniciando download de {total_urls} URLs...',
                'progress': 0,
                'total_urls': total_urls,
                'completed': 0,
                'failed': 0,
                'current_url': '',
                'results': []
            }
        )
        
        for i, url in enumerate(urls):
            try:
                # Progresso baseado no índice atual
                progress = int((i / total_urls) * 100)
                
                logger.info(f"[{task_id}] Processando URL {i+1}/{total_urls}: {url}")
                
                # Atualiza status
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'batch_processing',
                        'message': f'Processando URL {i+1}/{total_urls}',
                        'progress': progress,
                        'total_urls': total_urls,
                        'completed': completed,
                        'failed': failed,
                        'current_url': url,
                        'current_index': i + 1,
                        'results': results
                    }
                )
                
                # Processa URL individual usando a função existente
                single_result = process_single_video_for_batch(url, media_type, quality, bitrate, task_id, i)
                
                if single_result:
                    completed += 1
                    results.append({
                        'url': url,
                        'status': 'success',
                        'filename': single_result['filename'],
                        'title': single_result['title'],
                        'download_url': single_result['download_url']
                    })
                    
                    # Move para pasta se especificado
                    if folder_id:
                        DatabaseService.move_file_to_folder_by_filename(single_result['filename'], folder_id)
                        
                    logger.info(f"[{task_id}] URL {i+1} concluída com sucesso")
                else:
                    failed += 1
                    results.append({
                        'url': url,
                        'status': 'failed',
                        'error': 'Falha no processamento'
                    })
                    logger.warning(f"[{task_id}] URL {i+1} falhou")
                
            except Exception as e:
                failed += 1
                error_msg = str(e)
                logger.error(f"[{task_id}] Erro na URL {i+1} ({url}): {error_msg}")
                results.append({
                    'url': url,
                    'status': 'failed',
                    'error': error_msg
                })
        
        processing_time = round(time.time() - start_time)
        
        # Status final
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'message': f'Batch concluído: {completed} sucessos, {failed} falhas',
                'progress': 100,
                'total_urls': total_urls,
                'completed': completed,
                'failed': failed,
                'results': results
            }
        )
        
        return {
            'batch': True,
            'total_urls': total_urls,
            'completed': completed,
            'failed': failed,
            'results': results,
            'time_spend': f"{processing_time}s",
            'success_rate': round((completed / total_urls) * 100, 1) if total_urls > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"[{task_id}] Erro no batch download: {e}")
        raise

def process_single_video_for_batch(url, media_type, quality, bitrate, batch_task_id, index):
    """Processa um vídeo individual para batch download"""
    try:
        if not os.path.exists(Config.DOWNLOAD_FOLDER):
            os.makedirs(Config.DOWNLOAD_FOLDER)

        # Nome único para evitar conflitos
        unique_filename = f"batch_{batch_task_id}_{index}_{uuid.uuid4().hex[:8]}"
        
        # Configurações do yt-dlp
        ydl_opts = {
            'noplaylist': True,
            'quiet': True,
            'writeinfojson': False,
            'extract_flat': False,
            'ignoreerrors': True,
            'outtmpl': os.path.join(Config.DOWNLOAD_FOLDER, f"{unique_filename}.%(ext)s")
        }
        
        # Adiciona cookies se disponível
        cookies_path = ensure_cookies_available()
        if cookies_path and os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path

        if media_type == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': bitrate or '192'
            }]
            expected_extension = '.mp3'
        else:
            quality_filter = f"[height<={quality.replace('p', '')}]" if quality else ""
            ydl_opts['format'] = f'bestvideo{quality_filter}+bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }]
            expected_extension = '.mp4'

        # Download
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)

        # Encontra arquivo baixado
        found_file = None
        for filename in os.listdir(Config.DOWNLOAD_FOLDER):
            if filename.startswith(unique_filename) and not filename.endswith('.json'):
                found_file = os.path.join(Config.DOWNLOAD_FOLDER, filename)
                break

        if not found_file or not os.path.exists(found_file):
            raise FileNotFoundError(f"Arquivo não encontrado após download: {unique_filename}")

        # Nome final único
        final_filename = f"{uuid.uuid4().hex}{expected_extension}"
        final_path = os.path.join(Config.DOWNLOAD_FOLDER, final_filename)
        
        # Renomeia para nome final
        os.rename(found_file, final_path)
        
        # Salva no banco
        file_size_mb = round(os.path.getsize(final_path) / (1024 * 1024), 2)
        DatabaseService.save_media_file(final_filename, info_dict, media_type, file_size_mb)
        
        return {
            'filename': final_filename,
            'title': info_dict.get('title', 'N/A'),
            'download_url': f"{Config.BASE_URL}/api/download/{final_filename}"
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar vídeo individual para batch: {e}")
        return None