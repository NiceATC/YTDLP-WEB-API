import os
import logging
from flask import Flask

from config import Config
from database import create_tables
from services.database_service import DatabaseService
from services.file_service import FileService
from routes import register_routes

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY
logging.basicConfig(level=logging.INFO)

# Inicializa banco de dados
create_tables()

def setup_initial_data():
    """Configura dados iniciais se necessário"""
    # Cria usuário padrão se não existir
    if not DatabaseService.get_user():
        DatabaseService.create_or_update_user(Config.DEFAULT_PASSWORD)
    
    # Cria chave de API inicial se não existir
    if not DatabaseService.get_api_keys():
        DatabaseService.create_api_key("Chave Inicial")

setup_initial_data()

# Registra todas as rotas
register_routes(app)

if __name__ == '__main__':
    # Garante que o arquivo de cookies está disponível na inicialização
    FileService.ensure_cookies_available()
    app.run(host='0.0.0.0', port=Config.FLASK_RUN_PORT)