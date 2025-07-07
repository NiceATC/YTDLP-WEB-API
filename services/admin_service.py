import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from flask import current_app, redirect, url_for, flash
from celery.result import AsyncResult
from werkzeug.utils import secure_filename

from services.database_service import DatabaseService
from services.file_service import FileService
from config import Config
from tasks import celery

class AdminService:
    
    @staticmethod
    def get_downloaded_files():
        """Retorna arquivos baixados do banco de dados com verificação de existência"""
        files = DatabaseService.get_media_files()
        for file in files:
            file_path = os.path.join(Config.DOWNLOAD_FOLDER, file.filename)
            file.file_exists = os.path.exists(file_path)
            if file.file_exists:
                try:
                    file.actual_size_mb = round(os.path.getsize(file_path) / (1024 * 1024), 2)
                except:
                    file.actual_size_mb = 0
            else:
                file.actual_size_mb = 0
        return files

    @staticmethod
    def get_dashboard_stats() -> Dict[str, Any]:
        """Retorna estatísticas para o dashboard"""
        history = DatabaseService.get_request_history(limit=1000)
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        
        # Estatísticas gerais
        total_requests = len(history)
        successful_requests = len([h for h in history if h.status == 'completed'])
        failed_requests = len([h for h in history if h.status == 'failed'])
        processing_requests = len([h for h in history if h.status == 'processing'])
        
        # Estatísticas dos últimos 7 dias
        recent_history = [h for h in history if h.created_at >= week_ago]
        recent_total = len(recent_history)
        recent_successful = len([h for h in recent_history if h.status == 'completed'])
        recent_failed = len([h for h in recent_history if h.status == 'failed'])
        
        # Estatísticas por tipo
        audio_requests = len([h for h in history if h.request_data.get('type') == 'audio'])
        video_requests = len([h for h in history if h.request_data.get('type') == 'video'])
        
        # Arquivos
        files = AdminService.get_downloaded_files()
        total_files = len(files)
        missing_files = len([f for f in files if not f.file_exists])
        total_size_mb = sum([f.actual_size_mb for f in files if f.file_exists])
        
        return {
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'processing_requests': processing_requests,
            'success_rate': round((successful_requests / total_requests * 100) if total_requests > 0 else 0, 1),
            'recent_total': recent_total,
            'recent_successful': recent_successful,
            'recent_failed': recent_failed,
            'recent_success_rate': round((recent_successful / recent_total * 100) if recent_total > 0 else 0, 1),
            'audio_requests': audio_requests,
            'video_requests': video_requests,
            'total_files': total_files,
            'missing_files': missing_files,
            'total_size_mb': round(total_size_mb, 2),
            'week_comparison': {
                'requests_change': recent_total - (total_requests - recent_total) if (total_requests - recent_total) > 0 else recent_total,
                'success_change': recent_successful - (successful_requests - recent_successful) if (successful_requests - recent_successful) > 0 else recent_successful
            }
        }

    @staticmethod
    def get_processed_history():
        """Retorna histórico com status atualizados"""
        history = DatabaseService.get_request_history()
        
        # Atualiza status de tarefas em processamento
        for item in history:
            if item.response_data.get('status') == 'processing':
                task_id = item.response_data.get('task_id')
                if task_id:
                    task_result = AsyncResult(task_id, app=celery)
                    if task_result.state == 'SUCCESS':
                        item.response_data['status'] = 'completed'
                        item.response_data['result'] = task_result.result
                    elif task_result.state == 'FAILURE':
                        item.response_data['status'] = 'failed'
                        item.response_data['error'] = str(task_result.info)
        
        return history

    @staticmethod
    def test_api_endpoint(form_data):
        """Testa endpoint da API"""
        api_keys = DatabaseService.get_api_keys()
        if not api_keys:
            return {'error': 'Nenhuma chave de API válida configurada para teste.'}, 400
        
        api_key = api_keys[0].key
        
        # Garante que o arquivo de cookies está disponível antes do teste
        FileService.ensure_cookies_available()
        
        with current_app.test_client() as client:
            response = client.get('/api/media', query_string=form_data, headers={'X-API-Key': api_key})
            return response.get_json(), response.status_code

    @staticmethod
    def handle_cookie_upload(files):
        """Processa upload de arquivo de cookies"""
        if 'cookie_file' not in files:
            flash('Nenhum ficheiro selecionado.', 'error')
            return redirect(url_for('admin.dashboard') + '#settings')
        
        file = files['cookie_file']
        if file and file.filename != '':
            try:
                content = file.read()
                
                # Valida se o conteúdo parece ser um arquivo de cookies válido
                content_str = content.decode('utf-8', errors='ignore')
                if not content_str.strip():
                    flash('Arquivo de cookies está vazio.', 'error')
                    return redirect(url_for('admin.dashboard') + '#settings')
                
                # Salva no banco de dados
                DatabaseService.save_cookie_file(content, secure_filename(file.filename))
                
                # Escreve imediatamente no filesystem
                cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
                with open(cookies_path, 'wb') as f:
                    f.write(content)
                
                logging.info(f"Arquivo de cookies salvo: {len(content)} bytes em {cookies_path}")
                flash('Ficheiro de cookies atualizado com sucesso!', 'success')
                
            except Exception as e:
                logging.error(f"Erro ao processar arquivo de cookies: {e}")
                flash(f'Erro ao processar arquivo: {str(e)}', 'error')
        else:
            flash('Nenhum ficheiro selecionado.', 'error')
        
        return redirect(url_for('admin.dashboard') + '#settings')

    @staticmethod
    def delete_file(filename: str):
        """Remove arquivo do banco e filesystem"""
        # Remove do banco de dados
        DatabaseService.delete_media_file(filename)
        
        # Remove do filesystem se existir
        file_path = os.path.join(Config.DOWNLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)

    @staticmethod
    def cleanup_missing_files() -> int:
        """Remove registros de arquivos que não existem mais no filesystem"""
        files = DatabaseService.get_media_files()
        removed_count = 0
        
        for file in files:
            file_path = os.path.join(Config.DOWNLOAD_FOLDER, file.filename)
            if not os.path.exists(file_path):
                DatabaseService.delete_media_file(file.filename)
                removed_count += 1
        
        return removed_count