from functools import wraps
from flask import session, redirect, url_for, request, jsonify
from services.database_service import DatabaseService

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('auth.login'))
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