import os
import json
import logging
from dotenv import load_dotenv
from services.database_service import DatabaseService

load_dotenv()

class Config:
    BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:5000')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/mediaapi')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEFAULT_PASSWORD = os.getenv('DEFAULT_PASSWORD', 'admin')
    FLASK_RUN_PORT = int(os.getenv('FLASK_RUN_PORT', 5000))

    DOWNLOAD_FOLDER = 'downloads'

    @staticmethod
    def get_settings():
        """Retorna configurações do banco de dados com fallbacks"""
        try:
            settings = DatabaseService.get_all_settings()
            
            # Configurações padrão
            defaults = {
                "DEFAULT_RATE_LIMIT": "20 per minute",
                "TASK_COMPLETION_TIMEOUT": 60
            }
            
            # Mescla com padrões
            for key, default_value in defaults.items():
                if key not in settings:
                    settings[key] = default_value
                    DatabaseService.set_setting(key, default_value)
            
            return settings
        except Exception as e:
            logging.warning(f"Erro ao carregar configurações do banco: {e}")
            return {
                "DEFAULT_RATE_LIMIT": "20 per minute",
                "TASK_COMPLETION_TIMEOUT": 60
            }

    @staticmethod
    def save_settings(settings_data):
        """Salva configurações no banco de dados"""
        try:
            for key, value in settings_data.items():
                DatabaseService.set_setting(key, value)
        except Exception as e:
            logging.error(f"Erro ao salvar configurações: {e}")