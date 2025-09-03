import os
import uuid
import logging
import time
from datetime import datetime
from yt_dlp import YoutubeDL
from config import Config
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

class PlaylistProcessor:
    def __init__(self, task_self, base_opts):
        self.task_self = task_self
        self.base_opts = base_opts
        self.task_id = task_self.request.id

    def process(self, url, media_type, quality, bitrate):
        start_time = time.time()
        
        logger.info(f"[{self.task_id}] Processando playlist: {url}")
        
        # Atualiza status inicial
        self.task_self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'extracting',
                'message': 'Extraindo informações da playlist...',
                'progress': 5,
                'type': 'playlist'
            }
        )
        
        # Extrai informações da playlist
        extract_opts = self.base_opts.copy()
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
        
        logger.info(f"[{self.task_id}] Playlist com {total_videos} vídeos encontrada")
        
        # Atualiza status
        self.task_self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'downloading',
                'message': f'Baixando {total_videos} vídeos...',
                'progress': 10,
                'total_videos': total_videos,
                'completed_videos': 0,
                'failed_videos': 0,
                'type': 'playlist'
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
                logger.info(f"[{self.task_id}] Processando vídeo {i+1}/{total_videos}: {video_title}")
                
                # Atualiza status
                self.task_self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'downloading',
                        'message': f'Baixando: {video_title}',
                        'progress': download_progress,
                        'total_videos': total_videos,
                        'completed_videos': completed,
                        'failed_videos': failed,
                        'current_video': i + 1,
                        'current_title': video_title,
                        'type': 'playlist'
                    }
                )
                
                # URL do vídeo individual
                video_url = entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                
                # Processa vídeo individual
                result = self._process_single_video(video_url, media_type, quality, bitrate, i)
                
                if result:
                    completed += 1
                    results.append(result)
                    logger.info(f"[{self.task_id}] Vídeo {i+1} concluído: {result['filename']}")
                else:
                    failed += 1
                    logger.warning(f"[{self.task_id}] Vídeo {i+1} falhou: {video_title}")
                
            except Exception as e:
                failed += 1
                logger.error(f"[{self.task_id}] Erro ao processar vídeo {i+1}: {e}")
                continue
        
        if not results:
            raise Exception("Nenhum vídeo da playlist pôde ser processado")
        
        processing_time = round(time.time() - start_time)
        
        # Status final
        self.task_self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'message': f'Playlist concluída: {completed} sucessos, {failed} falhas',
                'progress': 100,
                'total_videos': total_videos,
                'completed_videos': completed,
                'failed_videos': failed,
                'type': 'playlist'
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

    def _process_single_video(self, url, media_type, quality, bitrate, index):
        """Processa um vídeo individual da playlist"""
        try:
            # Nome único para evitar conflitos
            unique_filename = f"playlist_{self.task_id}_{index}_{uuid.uuid4().hex[:8]}"
            
            # Configurações do yt-dlp
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

            # Download
            with YoutubeDL(video_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)

            # Encontra arquivo baixado
            found_file = None
            for filename in os.listdir(Config.DOWNLOAD_FOLDER):
                if filename.startswith(unique_filename) and not filename.endswith('.json'):
                    found_file = os.path.join(Config.DOWNLOAD_FOLDER, filename)
                    break

            if not found_file or not os.path.exists(found_file):
                logger.error(f"[{self.task_id}] Arquivo não encontrado após download: {unique_filename}")
                return None

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
                'download_url': f"{Config.BASE_URL}/api/download/{final_filename}",
                'duration': info_dict.get('duration_string', 'N/A'),
                'uploader': info_dict.get('uploader', 'N/A')
            }
            
        except Exception as e:
            logger.error(f"[{self.task_id}] Erro ao processar vídeo individual: {e}")
            return None