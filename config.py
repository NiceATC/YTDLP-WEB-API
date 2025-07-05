import os
import json
import base64
import logging
from dotenv import load_dotenv
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

load_dotenv()

class Config:
    BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:5000')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEFAULT_PASSWORD = os.getenv('DEFAULT_PASSWORD', 'admin')
    FLASK_RUN_PORT = int(os.getenv('FLASK_RUN_PORT', 5000))

    DOWNLOAD_FOLDER = 'downloads'
    AUTH_FILE = 'auth.json'
    HISTORY_FILE = 'history.json'
    SETTINGS_FILE = 'settings.json.enc'

    @staticmethod
    def _get_cipher_suite():
        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(Config.SECRET_KEY.encode('utf-8'))
        key = base64.urlsafe_b64encode(digest.finalize())
        return Fernet(key)

    @staticmethod
    def get_settings():
        cipher_suite = Config._get_cipher_suite()
        try:
            with open(Config.SETTINGS_FILE, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = cipher_suite.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))
        except (FileNotFoundError, json.JSONDecodeError, InvalidToken):
            logging.warning("Ficheiro de configurações inválido ou não encontrado. A redefinir para o padrão.")
            if os.path.exists(Config.SETTINGS_FILE):
                os.remove(Config.SETTINGS_FILE)
            
            return {
                "VALID_API_KEYS": ["chave_exemplo_inicial"],
                "DEFAULT_RATE_LIMIT": "20 per minute",
                "TASK_COMPLETION_TIMEOUT": 60
            }

    @staticmethod
    def save_settings(settings_data):
        cipher_suite = Config._get_cipher_suite()
        data_bytes = json.dumps(settings_data, indent=4).encode('utf-8')
        encrypted_data = cipher_suite.encrypt(data_bytes)
        with open(Config.SETTINGS_FILE, 'wb') as f:
            f.write(encrypted_data)

