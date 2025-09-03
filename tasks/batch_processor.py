import os
import uuid
import logging
import time
from yt_dlp import YoutubeDL
from config import Config
from services.database_service import DatabaseService

logger = logging.getLogger(__name__)

class BatchProcessor:
    def __init__(self, task_self, cookies_path):
        self.task_self = task_self
        self.cookies_path = cookies_path
        self.task_id = task_self.request.id

    def process(self, urls, media_type, quality, bitrate, folder_id):
        """Processa download em lote de múltiplas URLs"""
        start_time = time.time()
        
        try:
            logger.info(f"[{self.task_id}] Iniciando batch download com {len(urls)} URLs")
            
            total_urls = len(urls)
            completed = 0
            failed = 0
            results = []
            
            # Status inicial
            self.task_self.update_state(
                state='PROGRESS',
                meta={
                    'stage': 'batch_processing',
                    'message': f'Iniciando download de {total_urls} URLs...',
                    'progress': 0,
                    'total_urls': total_urls,
                    'completed': 0,
                    'failed': 0,
                    'current_url': '',
                    'results': [],
                    'type': 'batch'
                }
            )
            
            for i, url in enumerate(urls):
                try:
                    # Progresso baseado no índice atual
                    progress = int((i / total_urls) * 100)
                    
                    logger.info(f"[{self.task_id}] Processando URL {i+1}/{total_urls}: {url}")
                    
                    # Atualiza status
                    self.task_self.update_state(
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
                            'results': results,
                            'type': 'batch'
                        }
                    )
                    
                    # Processa URL individual
                    single_result = self._process_single_video_for_batch(url, media_type, quality, bitrate, i)
                    
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
                            
                        logger.info(f"[{self.task_id}] URL {i+1} concluída com sucesso")
                    else:
                        failed += 1
                        results.append({
                            'url': url,
                            'status': 'failed',
                            'error': 'Falha no processamento'
                        })
                        logger.warning(f"[{self.task_id}] URL {i+1} falhou")
                    
                except Exception as e:
                    failed += 1
                    error_msg = str(e)
                    logger.error(f"[{self.task_id}] Erro na URL {i+1} ({url}): {error_msg}")
                    results.append({
                        'url': url,
                        'status': 'failed',
                        'error': error_msg
                    })
            
            processing_time = round(time.time() - start_time)
            
            # Status final
            self.task_self.update_state(
                state='SUCCESS',
                meta={
                    'stage': 'completed',
                    'message': f'Batch concluído: {completed} sucessos, {failed} falhas',
                    'progress': 100,
                    'total_urls': total_urls,
                    'completed': completed,
                    'failed': failed,
                    'results': results,
                    'type': 'batch'
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
            logger.error(f"[{self.task_id}] Erro no batch download: {e}")
            raise

    def _process_single_video_for_batch(self, url, media_type, quality, bitrate, index):
        """Processa um vídeo individual para batch download"""
        try:
            if not os.path.exists(Config.DOWNLOAD_FOLDER):
                os.makedirs(Config.DOWNLOAD_FOLDER)

            # Nome único para evitar conflitos
            unique_filename = f"batch_{self.task_id}_{index}_{uuid.uuid4().hex[:8]}"
            
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
            if self.cookies_path and os.path.exists(self.cookies_path):
                ydl_opts['cookiefile'] = self.cookies_path

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