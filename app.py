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
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config
from tasks import celery, process_media

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
logging.basicConfig(level=logging.INFO)

def get_rate_limit_string():
    return Config.get_settings().get("DEFAULT_RATE_LIMIT", "20 per minute")

limiter = Limiter(
    get_rate_limit_string,
    app=app,
    storage_uri=Config.REDIS_URL
)

def setup_initial_files():
    if not os.path.exists(Config.AUTH_FILE):
        hashed_password = generate_password_hash(Config.DEFAULT_PASSWORD)
        with open(Config.AUTH_FILE, 'w') as f:
            json.dump({'password': hashed_password}, f)
    if not os.path.exists(Config.HISTORY_FILE):
        with open(Config.HISTORY_FILE, 'w') as f:
            json.dump([], f)
    if not os.path.exists(Config.SETTINGS_FILE):
        Config.save_settings(Config.get_settings())

setup_initial_files()

def get_password_hash():
    with open(Config.AUTH_FILE, 'r') as f:
        return json.load(f)['password']

def set_password_hash(new_password):
    hashed_password = generate_password_hash(new_password)
    with open(Config.AUTH_FILE, 'w') as f:
        json.dump({'password': hashed_password}, f)

def log_request_history(api_key, request_args, response_data):
    entry = {
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
        'api_key_used': f"{api_key[:4]}...{api_key[-4:]}",
        'request': request_args,
        'response': response_data
    }
    with open(Config.HISTORY_FILE, 'r+') as f:
        history = json.load(f)
        history.insert(0, entry)
        f.seek(0); f.truncate()
        json.dump(history, f, indent=4)

def get_request_history():
    with open(Config.HISTORY_FILE, 'r') as f:
        return json.load(f)

def get_downloaded_files():
    files = []
    if not os.path.exists(Config.DOWNLOAD_FOLDER):
        os.makedirs(Config.DOWNLOAD_FOLDER)
        
    for filename in os.listdir(Config.DOWNLOAD_FOLDER):
        if filename.endswith('.info.json'):
            continue

        filepath = os.path.join(Config.DOWNLOAD_FOLDER, filename)
        if os.path.isfile(filepath):
            metadata = {
                'title': 'N/A',
                'uploader': 'N/A',
                'thumbnail': 'https://placehold.co/128x72/1f2937/374151?text=Sem+Thumb',
            }
            info_filepath = f"{filepath}.info.json"
            if os.path.exists(info_filepath):
                try:
                    with open(info_filepath, 'r', encoding='utf-8') as f:
                        info_data = json.load(f)
                        metadata = {
                            'title': info_data.get('title', 'N/A'),
                            'uploader': info_data.get('uploader', 'N/A'),
                            'thumbnail': info_data.get('thumbnail', metadata['thumbnail']),
                            'duration_string': info_data.get('duration_string', 'N/A'),
                            'view_count': info_data.get('view_count', 0),
                            'like_count': info_data.get('like_count', 0),
                            'upload_date': info_data.get('upload_date', 'N/A'),
                            'webpage_url': info_data.get('webpage_url', '#'),
                            'description': info_data.get('description', 'Sem descrição.')
                        }
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logging.warning(f"Ficheiro de info corrompido: {info_filepath}")
                    pass

            files.append({
                'name': filename,
                'size_mb': round(os.path.getsize(filepath) / (1024 * 1024), 2),
                'metadata': metadata
            })
    return sorted(files, key=lambda x: x['name'], reverse=True)

def get_first_api_key():
    keys = Config.get_settings().get("VALID_API_KEYS", [])
    return keys[0] if keys else None

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
        valid_keys = Config.get_settings().get("VALID_API_KEYS", [])
        if not api_key or api_key not in valid_keys:
            return jsonify({'error': 'Chave de API inválida ou não fornecida. Use o header X-API-Key.'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'logged_in' in session: return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        password = request.form.get('password')
        if not password:
            flash('Senha é obrigatória.', 'error')
            return render_template('login.html')
        if check_password_hash(get_password_hash(), password):
            session['logged_in'] = True
            if password == Config.DEFAULT_PASSWORD: session['force_change'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Senha incorreta.', 'error')
    return render_template('login.html')

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if session.get('force_change'):
        return render_template('dashboard.html', force_change=True)

    history = get_request_history()
    for item in history:
        if item.get('response', {}).get('status') == 'processing':
            task_id = item['response'].get('task_id')
            if task_id:
                task_result = AsyncResult(task_id, app=celery)
                if task_result.state == 'SUCCESS':
                    item['response']['status'] = 'completed'
                    item['response']['result'] = task_result.result
                elif task_result.state == 'FAILURE':
                    item['response']['status'] = 'failed'
                    item['response']['error'] = str(task_result.info)

    settings = Config.get_settings()
    cookie_file_exists = os.path.exists('cookies.txt')
    return render_template('dashboard.html', 
                           history=history, 
                           files=get_downloaded_files(), 
                           settings=settings,
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
    settings = Config.get_settings()
    new_key = str(uuid.uuid4())
    settings['VALID_API_KEYS'].append(new_key)
    Config.save_settings(settings)
    flash(f'Nova chave de API criada: {new_key}', 'success')
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/admin/api-keys/delete', methods=['POST'])
@login_required
def delete_api_key():
    key_to_delete = request.form.get('api_key')
    settings = Config.get_settings()
    if key_to_delete in settings['VALID_API_KEYS']:
        settings['VALID_API_KEYS'].remove(key_to_delete)
        Config.save_settings(settings)
        flash('Chave de API removida com sucesso!', 'success')
    else:
        flash('Chave de API não encontrada.', 'error')
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/admin/cookies/delete', methods=['POST'])
@login_required
def delete_cookie_file():
    if os.path.exists('cookies.txt'):
        os.remove('cookies.txt')
        flash('Ficheiro de cookies removido com sucesso.', 'success')
    else:
        flash('Nenhum ficheiro de cookies para remover.', 'info')
    return redirect(url_for('admin_dashboard') + '#settings')

@app.route('/admin/test-api', methods=['POST'])
@login_required
def test_api():
    api_key = get_first_api_key()
    if not api_key: return jsonify({'error': 'Nenhuma chave de API válida configurada para teste.'}), 400
    form_data = request.json
    with app.test_client() as client:
        response = client.get('/api/media', query_string=form_data, headers={'X-API-Key': api_key})
        return response.get_json(), response.status_code

@app.route('/admin/change-password', methods=['POST'])
@login_required
def change_password():
    set_password_hash(request.form.get('new_password'))
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
        file.save(secure_filename('cookies.txt'))
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
    type: str; url: Optional[str] = None; name: Optional[str] = None; quality: Optional[str] = None; bitrate: Optional[str] = None
    @validator('type')
    def type_must_be_valid(cls, v):
        if v.lower() not in ['audio', 'video']: raise ValueError("Tipo deve ser 'audio' ou 'video'")
        return v.lower()
    @validator('name')
    def url_or_name_must_exist(cls, v, values):
        if not values.get('url') and not v: raise ValueError('URL ou nome é obrigatório')
        return v

@app.route('/')
def documentation():
    return render_template('docs.html')

@app.route('/api/health')
def health_check():
    try:
        Redis.from_url(Config.REDIS_URL).ping(); redis_status = 'ok'
    except RedisConnectionError: redis_status = 'error'
    status = 'ok' if redis_status == 'ok' else 'error'
    return jsonify({'status': status, 'dependencies': {'redis': redis_status}}), 200 if status == 'ok' else 503

@app.route('/api/media', methods=['GET'])
@require_api_key
@limiter.limit(lambda: get_rate_limit_string())
def download_media():
    api_key = request.headers.get('X-API-Key')
    try:
        data = MediaRequest(**request.args.to_dict())
    except ValidationError as e:
        return jsonify({'error': 'Dados de entrada inválidos', 'details': e.errors()}), 400
    
    search_query = data.url if data.url else f"ytsearch:{data.name}"
    task = process_media.delay(search_query, data.type, data.quality, data.bitrate)
    timeout = Config.get_settings().get("TASK_COMPLETION_TIMEOUT", 60)

    try:
        result = task.get(timeout=timeout)
        if task.failed():
            raise task.info
        response_data = {"status": "completed", "result": result}
        log_request_history(api_key, request.args.to_dict(), response_data)
        return jsonify(response_data), 200
    except TimeoutError:
        response_data = {"status": "processing", "task_id": task.id, "check_status_url": f"{Config.BASE_URL}/api/tasks/{task.id}"}
        log_request_history(api_key, request.args.to_dict(), response_data)
        return jsonify(response_data), 202
    except Exception as e:
        logging.error(f"A tarefa {task.id} falhou durante a execução: {e}")
        error_info = str(e)
        response_data = {"status": "failed", "task_id": task.id, "error": error_info}
        log_request_history(api_key, request.args.to_dict(), response_data)
        return jsonify(response_data), 500

@app.route('/api/tasks/<task_id>', methods=['GET'])
@require_api_key
def get_task_status(task_id):
    task_result = AsyncResult(task_id, app=celery)
    if task_result.state == 'PENDING': response = {'status': 'pending', 'message': 'A tarefa ainda não foi iniciada.'}
    elif task_result.state == 'SUCCESS': response = {'status': 'completed', 'result': task_result.result}
    elif task_result.state == 'FAILURE': response = {'status': 'failed', 'message': str(task_result.info)}
    else: response = {'status': task_result.state}
    return jsonify(response)

@app.route('/api/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(app.config['DOWNLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT)
