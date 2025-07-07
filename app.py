import os
import json
import logging
from functools import wraps
from typing import Optional
from datetime import datetime, timedelta
import uuid

from celery.result import AsyncResult, TimeoutError
from flask import (Flask, flash, jsonify, redirect, render_template, request,
                   send_from_directory, session, url_for)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from pydantic import BaseModel, ValidationError, validator
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from werkzeug.utils import secure_filename

from config import Config
from tasks import celery, process_media
from database import create_tables
from services.database_service import DatabaseService

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
logging.basicConfig(level=logging.INFO)

# Inicializa banco de dados
create_tables()

def get_rate_limit_string():
    return Config.get_settings().get("DEFAULT_RATE_LIMIT", "20 per minute")

limiter = Limiter(
    get_rate_limit_string,
    app=app,
    storage_uri=Config.REDIS_URL
)

def setup_initial_data():
    """Configura dados iniciais se necessário"""
    # Cria usuário padrão se não existir
    if not DatabaseService.get_user():
        DatabaseService.create_or_update_user(Config.DEFAULT_PASSWORD)
    
    # Cria chave de API inicial se não existir
    if not DatabaseService.get_api_keys():
        DatabaseService.create_api_key("Chave Inicial")

setup_initial_data()

def ensure_cookie_file_exists():
    """Garante que o arquivo de cookies existe no filesystem se estiver no banco"""
    try:
        cookie_file = DatabaseService.get_cookie_file()
        if cookie_file:
            cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
            # Sempre reescreve o arquivo para garantir que está atualizado
            with open(cookies_path, 'wb') as f:
                f.write(cookie_file.content)
            logging.info(f"Arquivo de cookies escrito em: {cookies_path}")
            return True
        else:
            # Remove arquivo se não há cookies no banco
            cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
            if os.path.exists(cookies_path):
                os.remove(cookies_path)
                logging.info("Arquivo de cookies removido (não há cookies no banco)")
        return False
    except Exception as e:
        logging.error(f"Erro ao escrever arquivo de cookies: {e}")
        return False

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

def get_dashboard_stats():
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
    files = get_downloaded_files()
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or not DatabaseService.validate_api_key(api_key):
            return jsonify({'error': 'Chave de API inválida ou não fornecida. Use o header X-API-Key.'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session: 
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        if not password:
            flash('Senha é obrigatória.', 'error')
            return render_template('login.html')
        
        if DatabaseService.verify_password(password):
            session['logged_in'] = True
            if password == Config.DEFAULT_PASSWORD: 
                session['force_change'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Senha incorreta.', 'error')
    
    return render_template('login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if session.get('force_change'):
        return render_template('dashboard.html', force_change=True)

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

    settings = Config.get_settings()
    api_keys = DatabaseService.get_api_keys()
    cookie_file_exists = DatabaseService.get_cookie_file() is not None
    stats = get_dashboard_stats()
    
    return render_template('dashboard.html', 
                           history=history, 
                           files=get_downloaded_files(), 
                           settings=settings,
                           api_keys=api_keys,
                           cookie_file_exists=cookie_file_exists,
                           stats=stats)

@app.route('/admin/history/delete/<int:history_id>', methods=['POST'])
@login_required
def delete_history_item():
    history_id = request.json.get('id')
    if DatabaseService.delete_history_item(history_id):
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/admin/history/clear', methods=['POST'])
@login_required
def clear_history():
    DatabaseService.clear_history()
    flash('Histórico limpo com sucesso!', 'success')
    return redirect(url_for('admin_dashboard') + '#history')

@app.route('/admin/files/delete/<filename>', methods=['POST'])
@login_required
def delete_file():
    filename = request.json.get('filename')
    try:
        # Remove do banco de dados
        DatabaseService.delete_media_file(filename)
        
        # Remove do filesystem se existir
        file_path = os.path.join(Config.DOWNLOAD_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Erro ao deletar arquivo {filename}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/files/cleanup', methods=['POST'])
@login_required
def cleanup_missing_files():
    """Remove registros de arquivos que não existem mais no filesystem"""
    files = DatabaseService.get_media_files()
    removed_count = 0
    
    for file in files:
        file_path = os.path.join(Config.DOWNLOAD_FOLDER, file.filename)
        if not os.path.exists(file_path):
            DatabaseService.delete_media_file(file.filename)
            removed_count += 1
    
    flash(f'{removed_count} registros de arquivos inexistentes foram removidos.', 'success')
    return redirect(url_for('admin_dashboard') + '#files')

@app.route('/admin/settings', methods=['POST'])
@login_required
def update_settings():
    settings = Config.get_settings()
    settings['DEFAULT_RATE_LIMIT'] = request.form.get('rate_limit', '20 per minute')
    settings['TASK_COMPLETION_TIMEOUT'] = int(request.form.get('timeout', 10))
    Config.save_settings(settings)
    flash('Configurações gerais salvas com sucesso!', 'success')
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/admin/api-keys/new', methods=['POST'])
@login_required
def new_api_key():
    name = request.form.get('name', '')
    api_key = DatabaseService.create_api_key(name)
    flash(f'Nova chave de API criada: {api_key.key}', 'success')
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/admin/api-keys/delete', methods=['POST'])
@login_required
def delete_api_key():
    key_to_delete = request.form.get('api_key')
    if DatabaseService.delete_api_key(key_to_delete):
        flash('Chave de API removida com sucesso!', 'success')
    else:
        flash('Chave de API não encontrada.', 'error')
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/admin/cookies/delete', methods=['POST'])
@login_required
def delete_cookie_file():
    if DatabaseService.delete_cookie_file():
        # Remove também do filesystem
        cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
        if os.path.exists(cookies_path):
            os.remove(cookies_path)
            logging.info("Arquivo de cookies removido do filesystem")
        flash('Ficheiro de cookies removido com sucesso.', 'success')
    else:
        flash('Nenhum ficheiro de cookies para remover.', 'info')
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/admin/test-api', methods=['POST'])
@login_required
def test_api():
    api_keys = DatabaseService.get_api_keys()
    if not api_keys:
        return jsonify({'error': 'Nenhuma chave de API válida configurada para teste.'}), 400
    
    api_key = api_keys[0].key
    form_data = request.json
    
    # Garante que o arquivo de cookies está disponível antes do teste
    ensure_cookie_file_exists()
    
    with app.test_client() as client:
        response = client.get('/api/media', query_string=form_data, headers={'X-API-Key': api_key})
        return response.get_json(), response.status_code

@app.route('/admin/change-password', methods=['POST'])
@login_required
def change_password():
    new_password = request.form.get('new_password')
    DatabaseService.create_or_update_user(new_password)
    session.pop('force_change', None)
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload-cookies', methods=['POST'])
@login_required
def upload_cookies():
    if 'cookie_file' not in request.files:
        flash('Nenhum ficheiro selecionado.', 'error')
        return redirect(url_for('admin_dashboard') + '#settings')
    
    file = request.files['cookie_file']
    if file and file.filename != '':
        try:
            content = file.read()
            
            # Valida se o conteúdo parece ser um arquivo de cookies válido
            content_str = content.decode('utf-8', errors='ignore')
            if not content_str.strip():
                flash('Arquivo de cookies está vazio.', 'error')
                return redirect(url_for('admin_dashboard') + '#settings')
            
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
    
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('login'))

class MediaRequest(BaseModel):
    type: str
    url: str
    quality: Optional[str] = None
    bitrate: Optional[str] = None
    
    @validator('type')
    def type_must_be_valid(cls, v):
        if v.lower() not in ['audio', 'video']:
            raise ValueError("Tipo deve ser 'audio' ou 'video'")
        return v.lower()
    
    @validator('url')
    def url_must_be_provided(cls, v):
        if not v or not v.strip():
            raise ValueError('URL é obrigatória')
        return v.strip()

@app.route('/')
def documentation():
    return render_template('docs.html')

@app.route('/api/health')
def health_check():
    try:
        Redis.from_url(Config.REDIS_URL).ping()
        redis_status = 'ok'
    except RedisConnectionError: 
        redis_status = 'error'
    
    try:
        DatabaseService.get_user()
        db_status = 'ok'
    except:
        db_status = 'error'
    
    # Verifica se o arquivo de cookies está sincronizado
    cookie_status = 'ok'
    try:
        cookie_file = DatabaseService.get_cookie_file()
        cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
        
        if cookie_file and not os.path.exists(cookies_path):
            cookie_status = 'needs_sync'
        elif not cookie_file and os.path.exists(cookies_path):
            cookie_status = 'orphaned_file'
    except:
        cookie_status = 'error'
    
    status = 'ok' if redis_status == 'ok' and db_status == 'ok' and cookie_status == 'ok' else 'warning'
    return jsonify({
        'status': status, 
        'dependencies': {
            'redis': redis_status,
            'database': db_status,
            'cookies': cookie_status
        }
    }), 200 if status == 'ok' else 503

@app.route('/api/media', methods=['GET'])
@require_api_key
@limiter.limit(lambda: get_rate_limit_string())
def download_media():
    api_key = request.headers.get('X-API-Key')
    try:
        data = MediaRequest(**request.args.to_dict())
    except ValidationError as e:
        return jsonify({'error': 'Dados de entrada inválidos', 'details': e.errors()}), 400
    
    # CRÍTICO: Garante que o arquivo de cookies está sempre disponível
    ensure_cookie_file_exists()
    
    task = process_media.delay(data.url, data.type, data.quality, data.bitrate)
    timeout = Config.get_settings().get("TASK_COMPLETION_TIMEOUT", 60)

    try:
        result = task.get(timeout=timeout)
        if task.failed():
            raise task.info
        
        response_data = {"status": "completed", "result": result}
        DatabaseService.log_request(api_key, request.args.to_dict(), response_data, "completed")
        return jsonify(response_data), 200
    except TimeoutError:
        response_data = {
            "status": "processing", 
            "task_id": task.id, 
            "check_status_url": f"{Config.BASE_URL}/api/tasks/{task.id}"
        }
        DatabaseService.log_request(api_key, request.args.to_dict(), response_data, "processing")
        return jsonify(response_data), 202
    except Exception as e:
        logging.error(f"A tarefa {task.id} falhou durante a execução: {e}")
        error_info = str(e)
        response_data = {"status": "failed", "task_id": task.id, "error": error_info}
        DatabaseService.log_request(api_key, request.args.to_dict(), response_data, "failed")
        return jsonify(response_data), 500

@app.route('/api/tasks/<task_id>', methods=['GET'])
@require_api_key
def get_task_status(task_id):
    task_result = AsyncResult(task_id, app=celery)
    if task_result.state == 'PENDING': 
        response = {'status': 'pending', 'message': 'A tarefa ainda não foi iniciada.'}
    elif task_result.state == 'SUCCESS': 
        response = {'status': 'completed', 'result': task_result.result}
    elif task_result.state == 'FAILURE': 
        response = {'status': 'failed', 'message': str(task_result.info)}
    else: 
        response = {'status': task_result.state}
    return jsonify(response)

@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Garante que o arquivo de cookies está disponível na inicialização
    ensure_cookie_file_exists()
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT)