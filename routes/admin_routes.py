import os
import logging
from flask import Blueprint, render_template, request, session, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
from services.database_service import DatabaseService
from services.file_service import FileService
from services.admin_service import AdminService
from utils.decorators import login_required
from config import Config

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
def dashboard():
    if session.get('force_change'):
        return render_template('admin/dashboard.html', force_change=True, stats={"chart_data": [],"audio_requests": 0,"video_requests": 0})
    try:
        history = AdminService.get_processed_history()
        settings = Config.get_settings()
        api_keys = DatabaseService.get_api_keys()
        cookie_file_exists = DatabaseService.get_cookie_file() is not None
        cookie_status = FileService.check_cookie_status()
        stats = AdminService.get_dashboard_stats()
        files = AdminService.get_downloaded_files()
        folders = DatabaseService.get_folders()
        app_settings = DatabaseService.get_app_settings()
        
        return render_template('admin/dashboard.html', 
                               history=history, 
                               files=files, 
                               folders=folders,
                               app_settings=app_settings,
                               settings=settings,
                               api_keys=api_keys,
                               cookie_file_exists=cookie_file_exists,
                               cookie_status=cookie_status,
                               stats=stats)
    except Exception as e:
        logging.error(f"Erro no dashboard: {e}")
        flash('Erro ao carregar dashboard. Tente novamente.', 'error')
        return redirect(url_for('auth.login'))

@admin_bp.route('/settings', methods=['POST'])
@login_required
def update_settings():
    settings = Config.get_settings()
    settings['DEFAULT_RATE_LIMIT'] = request.form.get('rate_limit', '20 per minute')
    settings['TASK_COMPLETION_TIMEOUT'] = int(request.form.get('timeout', 10))
    settings['PUBLIC_DOWNLOAD_LIMIT'] = request.form.get('public_limit', '5 per hour')
    settings['MAX_FILE_SIZE_MB'] = int(request.form.get('max_file_size', 500))
    settings['AUTO_CLEANUP_DAYS'] = int(request.form.get('auto_cleanup_days', 30))
    Config.save_settings(settings)
    flash('Configurações gerais salvas com sucesso!', 'success')
    return redirect(url_for('admin.dashboard') + '#settings')

@admin_bp.route('/api-keys/new', methods=['POST'])
@login_required
def new_api_key():
    try:
        name = request.form.get('name', '') or request.json.get('name', '')
        api_key = DatabaseService.create_api_key(name)
        
        return jsonify({
            'success': True,
            'api_key': {
                'id': api_key.id,
                'key': api_key.key,
                'name': api_key.name,
                'created_at': api_key.created_at.strftime('%d/%m/%Y %H:%M'),
                'last_used': None
            }
        })
    except Exception as e:
        logging.error(f"Erro ao criar API key: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/api-keys/delete', methods=['POST'])
@login_required
def delete_api_key():
    try:
        key_to_delete = request.form.get('api_key') or request.json.get('api_key')
        if DatabaseService.delete_api_key(key_to_delete):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Chave não encontrada'}), 404
    except Exception as e:
        logging.error(f"Erro ao deletar API key: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/cookies/sync', methods=['POST'])
@login_required
def sync_cookies():
    try:
        FileService.ensure_cookies_available()
        cookie_status = FileService.check_cookie_status()
        return jsonify({
            'success': True, 
            'status': cookie_status,
            'message': 'Cookies sincronizados com sucesso!'
        })
    except Exception as e:
        logging.error(f"Erro ao sincronizar cookies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/cookies/delete', methods=['POST'])
@login_required
def delete_cookie_file():
    try:
        if DatabaseService.delete_cookie_file():
            cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
            if os.path.exists(cookies_path):
                os.remove(cookies_path)
                logging.info("Arquivo de cookies removido do filesystem")
            return jsonify({'success': True, 'message': 'Cookies removidos com sucesso'})
        else:
            return jsonify({'success': False, 'error': 'Nenhum arquivo de cookies para remover'}), 404
    except Exception as e:
        logging.error(f"Erro ao deletar cookies: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
    return jsonify({'success': True})

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

@admin_bp.route('/files/move', methods=['POST'])
@login_required
def move_file():
    try:
        file_id = request.form.get('file_id')
        folder_id = request.form.get('folder_id')
        
        if not file_id:
            return jsonify({'success': False, 'error': 'ID do arquivo é obrigatório'}), 400
        
        # Convert empty string to None for root folder
        folder_id = int(folder_id) if folder_id else None
        
        if DatabaseService.move_file_to_folder(int(file_id), folder_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Arquivo não encontrado'}), 404
    except Exception as e:
        logging.error(f"Erro ao mover arquivo: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/files/filter')
@login_required
def filter_files():
    search = request.args.get('search', '')
    folder_id = request.args.get('folder_id')
    media_type = request.args.get('media_type')
    sort = request.args.get('sort', 'created_at-desc')
    
    sort_by, sort_order = sort.split('-')
    
    files = DatabaseService.get_media_files(
        folder_id=int(folder_id) if folder_id else None,
        search=search,
        media_type=media_type,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=50
    )
    
    # Verificar existência dos arquivos
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
    
    # Renderizar apenas os cards dos arquivos
    html = render_template('admin/components/file_cards.html', files=files)
    
    return jsonify({
        'success': True,
        'html': html,
        'count': len(files)
    })

@admin_bp.route('/files/cleanup', methods=['POST'])
@login_required
def cleanup_missing_files():
    removed_count = AdminService.cleanup_missing_files()
    return jsonify({'success': True, 'removed_count': removed_count})

@admin_bp.route('/app-settings', methods=['POST'])
@login_required
def update_app_settings():
    try:
        app_settings = DatabaseService.update_app_settings(
            app_name=request.form.get('app_name', 'YTDL Web API'),
            app_logo=request.form.get('app_logo', ''),
            primary_color=request.form.get('primary_color', '#0891b2'),
            secondary_color=request.form.get('secondary_color', '#0e7490'),
            favicon_url=request.form.get('favicon_url', ''),
            footer_text=request.form.get('footer_text', '© 2024 YTDL Web API')
        )
        
        # Apply settings immediately to session for instant feedback
        session['app_settings'] = {
            'app_name': app_settings.app_name,
            'app_logo': app_settings.app_logo,
            'primary_color': app_settings.primary_color,
            'secondary_color': app_settings.secondary_color,
            'favicon_url': app_settings.favicon_url,
            'footer_text': app_settings.footer_text
        }
        
        flash('Configurações da aplicação salvas com sucesso!', 'success')
        return jsonify({'success': True, 'settings': session['app_settings']})
    except Exception as e:
        logging.error(f"Erro ao salvar configurações da aplicação: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/folders/create', methods=['POST'])
@login_required
def create_folder():
    try:
        folder_name = request.form.get('folder_name')
        if not folder_name or not folder_name.strip():
            return jsonify({'success': False, 'error': 'Nome da pasta é obrigatório'}), 400
        
        folder = DatabaseService.create_folder(folder_name.strip())
        return jsonify({
            'success': True, 
            'folder': {
                'id': folder.id,
                'name': folder.name,
                'created_at': folder.created_at.strftime('%d/%m/%Y')
            }
        })
    except Exception as e:
        logging.error(f"Erro ao criar pasta: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/folders/delete', methods=['POST'])
@login_required
def delete_folder():
    try:
        folder_id = request.json.get('folder_id')
        if not folder_id:
            return jsonify({'success': False, 'error': 'ID da pasta é obrigatório'}), 400
        
        if DatabaseService.delete_folder(int(folder_id)):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Pasta não encontrada'}), 404
    except Exception as e:
        logging.error(f"Erro ao deletar pasta: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/batch-download', methods=['POST'])
@login_required
def batch_download():
    try:
        batch_name = request.form.get('batch_name')
        urls_text = request.form.get('urls')
        media_type = request.form.get('type')
        quality = request.form.get('quality')
        bitrate = request.form.get('bitrate')
        folder_id = request.form.get('folder_id')
        
        if not batch_name or not urls_text or not media_type:
            return jsonify({'success': False, 'error': 'Campos obrigatórios não preenchidos'}), 400
        
        urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
        
        if not urls:
            return jsonify({'success': False, 'error': 'Nenhuma URL fornecida'}), 400
        
        # Inicia tarefa de batch download
        from tasks import process_batch_download
        task = process_batch_download.delay(
            urls=urls,
            media_type=media_type,
            quality=quality,
            bitrate=bitrate,
            folder_id=int(folder_id) if folder_id else None,
            batch_name=batch_name,
            task_id=None  # Será definido automaticamente pelo Celery
        )
        
        return jsonify({
            'success': True, 
            'task_id': task.id,
            'total_urls': len(urls),
            'message': f'Download em lote "{batch_name}" iniciado com {len(urls)} URLs'
        })
    except Exception as e:
        logging.error(f"Erro ao criar download em lote: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_bp.route('/tasks/<task_id>/status', methods=['GET'])
@login_required
def get_task_status_admin(task_id):
    """Retorna status detalhado de uma tarefa para o admin"""
    try:
        from celery.result import AsyncResult
        from tasks import celery
        
        task_result = AsyncResult(task_id, app=celery)
        
        if task_result.state == 'PENDING':
            response = {
                'state': 'PENDING',
                'message': 'Tarefa aguardando processamento...',
                'progress': 0
            }
        elif task_result.state == 'PROGRESS':
            response = {
                'state': 'PROGRESS',
                'progress': task_result.info.get('progress', 0),
                'message': task_result.info.get('message', 'Processando...'),
                'stage': task_result.info.get('stage', 'unknown'),
                **task_result.info
            }
        elif task_result.state == 'SUCCESS':
            response = {
                'state': 'SUCCESS',
                'message': 'Tarefa concluída com sucesso!',
                'progress': 100,
                'result': task_result.result
            }
        elif task_result.state == 'FAILURE':
            response = {
                'state': 'FAILURE',
                'message': f'Tarefa falhou: {str(task_result.info)}',
                'progress': 0,
                'error': str(task_result.info)
            }
        else:
            response = {
                'state': task_result.state,
                'message': f'Estado: {task_result.state}',
                'progress': 0
            }
        
        return jsonify(response)
    except Exception as e:
        logging.error(f"Erro ao obter status da tarefa {task_id}: {e}")
        return jsonify({
            'state': 'ERROR',
            'message': f'Erro ao obter status: {str(e)}',
            'progress': 0
        }), 500