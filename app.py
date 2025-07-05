import os
import json
import logging
from functools import wraps
from typing import Optional
from datetime import datetime
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

def write_cookie_file_if_exists():
    """Escreve o arquivo de cookies do banco para o filesystem se existir"""
    cookie_file = DatabaseService.get_cookie_file()
    if cookie_file:
        with open('cookies.txt', 'wb') as f:
            f.write(cookie_file.content)
        return True
    return False

def get_downloaded_files():
    """Retorna arquivos baixados do banco de dados"""
    return DatabaseService.get_media_files()

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
    
    return render_template('dashboard.html', 
                           history=history, 
                           files=get_downloaded_files(), 
                           settings=settings,
                           api_keys=api_keys,
                           cookie_file_exists=cookie_file_exists)

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
        if os.path.exists('cookies.txt'):
            os.remove('cookies.txt')
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
        content = file.read()
        DatabaseService.save_cookie_file(content, secure_filename(file.filename))
        
        # Escreve também no filesystem para uso imediato
        with open('cookies.txt', 'wb') as f:
            f.write(content)
        
        flash('Ficheiro de cookies atualizado com sucesso!', 'success')
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
    
    status = 'ok' if redis_status == 'ok' and db_status == 'ok' else 'error'
    return jsonify({
        'status': status, 
        'dependencies': {
            'redis': redis_status,
            'database': db_status
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
    
    # Escreve arquivo de cookies se existir no banco
    write_cookie_file_if_exists()
    
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
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT)