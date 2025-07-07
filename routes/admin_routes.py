import os
import logging
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from services.database_service import DatabaseService
from services.admin_service import AdminService
from utils.decorators import login_required
from config import Config

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if session.get('force_change'):
        return render_template('admin/dashboard.html', force_change=True)

    history = AdminService.get_processed_history()
    settings = Config.get_settings()
    api_keys = DatabaseService.get_api_keys()
    cookie_file_exists = DatabaseService.get_cookie_file() is not None
    stats = AdminService.get_dashboard_stats()
    files = AdminService.get_downloaded_files()
    
    return render_template('admin/dashboard.html', 
                           history=history, 
                           files=files, 
                           settings=settings,
                           api_keys=api_keys,
                           cookie_file_exists=cookie_file_exists,
                           stats=stats)

@admin_bp.route('/settings', methods=['POST'])
@login_required
def update_settings():
    settings = Config.get_settings()
    settings['DEFAULT_RATE_LIMIT'] = request.form.get('rate_limit', '20 per minute')
    settings['TASK_COMPLETION_TIMEOUT'] = int(request.form.get('timeout', 10))
    Config.save_settings(settings)
    flash('Configurações gerais salvas com sucesso!', 'success')
    return redirect(url_for('admin.dashboard') + '#settings')

@admin_bp.route('/api-keys/new', methods=['POST'])
@login_required
def new_api_key():
    name = request.form.get('name', '')
    api_key = DatabaseService.create_api_key(name)
    flash(f'Nova chave de API criada: {api_key.key}', 'success')
    return redirect(url_for('admin.dashboard') + '#settings')

@admin_bp.route('/api-keys/delete', methods=['POST'])
@login_required
def delete_api_key():
    key_to_delete = request.form.get('api_key')
    if DatabaseService.delete_api_key(key_to_delete):
        flash('Chave de API removida com sucesso!', 'success')
    else:
        flash('Chave de API não encontrada.', 'error')
    return redirect(url_for('admin.dashboard') + '#settings')

@admin_bp.route('/cookies/delete', methods=['POST'])
@login_required
def delete_cookie_file():
    if DatabaseService.delete_cookie_file():
        cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
        if os.path.exists(cookies_path):
            os.remove(cookies_path)
            logging.info("Arquivo de cookies removido do filesystem")
        flash('Ficheiro de cookies removido com sucesso.', 'success')
    else:
        flash('Nenhum ficheiro de cookies para remover.', 'info')
    return redirect(url_for('admin.dashboard') + '#settings')

@admin_bp.route('/test-api', methods=['POST'])
@login_required
def test_api():
    return AdminService.test_api_endpoint(request.json)

@admin_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    new_password = request.form.get('new_password')
    DatabaseService.create_or_update_user(new_password)
    session.pop('force_change', None)
    flash('Senha alterada com sucesso!', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/upload-cookies', methods=['POST'])
@login_required
def upload_cookies():
    return AdminService.handle_cookie_upload(request.files)

@admin_bp.route('/history/delete', methods=['POST'])
@login_required
def delete_history_item():
    history_id = request.json.get('id')
    if DatabaseService.delete_history_item(history_id):
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@admin_bp.route('/history/clear', methods=['POST'])
@login_required
def clear_history():
    DatabaseService.clear_history()
    flash('Histórico limpo com sucesso!', 'success')
    return redirect(url_for('admin.dashboard') + '#history')

@admin_bp.route('/files/delete', methods=['POST'])
@login_required
def delete_file():
    filename = request.json.get('filename')
    try:
        AdminService.delete_file(filename)
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Erro ao deletar arquivo {filename}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/files/cleanup', methods=['POST'])
@login_required
def cleanup_missing_files():
    removed_count = AdminService.cleanup_missing_files()
    flash(f'{removed_count} registros de arquivos inexistentes foram removidos.', 'success')
    return redirect(url_for('admin.dashboard') + '#files')