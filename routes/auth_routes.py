from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from services.database_service import DatabaseService
from config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if 'logged_in' in session: 
            return redirect(url_for('admin.dashboard'))
        
        if request.method == 'POST':
            password = request.form.get('password')
            if not password:
                flash('Senha é obrigatória.', 'error')
                return render_template('auth/login.html')
            
            if DatabaseService.verify_password(password):
                session['logged_in'] = True
                if password == Config.DEFAULT_PASSWORD: 
                    session['force_change'] = True
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Senha incorreta.', 'error')
        
        return render_template('auth/login.html')
    except Exception as e:
        logging.error(f"Erro no login: {e}")
        flash('Erro interno. Tente novamente.', 'error')
        return render_template('auth/login.html')
    
    if request.method == 'POST':
        password = request.form.get('password')
        if not password:
            flash('Senha é obrigatória.', 'error')
            return render_template('auth/login.html')
        
        if DatabaseService.verify_password(password):
            session['logged_in'] = True
            if password == Config.DEFAULT_PASSWORD: 
                session['force_change'] = True
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Senha incorreta.', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('auth.login'))