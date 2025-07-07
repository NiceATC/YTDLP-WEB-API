import logging
from flask import Blueprint, jsonify, request, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from celery.result import AsyncResult, TimeoutError
from pydantic import BaseModel, ValidationError, validator
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from config import Config
from tasks import celery, process_media
from services.database_service import DatabaseService
from services.file_service import FileService
from utils.decorators import require_api_key

api_bp = Blueprint('api', __name__)

def get_rate_limit_string():
    return Config.get_settings().get("DEFAULT_RATE_LIMIT", "20 per minute")

limiter = Limiter(
    get_rate_limit_string,
    storage_uri=Config.REDIS_URL
)

class MediaRequest(BaseModel):
    type: str
    url: str
    quality: str = None
    bitrate: str = None
    
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

@api_bp.route('/health')
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
    
    cookie_status = FileService.check_cookie_status()
    
    status = 'ok' if redis_status == 'ok' and db_status == 'ok' and cookie_status == 'ok' else 'warning'
    return jsonify({
        'status': status, 
        'dependencies': {
            'redis': redis_status,
            'database': db_status,
            'cookies': cookie_status
        }
    }), 200 if status == 'ok' else 503

@api_bp.route('/media', methods=['GET'])
@require_api_key
@limiter.limit(lambda: get_rate_limit_string())
def download_media():
    api_key = request.headers.get('X-API-Key')
    try:
        data = MediaRequest(**request.args.to_dict())
    except ValidationError as e:
        return jsonify({'error': 'Dados de entrada inválidos', 'details': e.errors()}), 400
    
    FileService.ensure_cookies_available()
    
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

@api_bp.route('/tasks/<task_id>', methods=['GET'])
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

@api_bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    return send_from_directory(Config.DOWNLOAD_FOLDER, filename)