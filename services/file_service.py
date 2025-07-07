import os
import logging
from services.database_service import DatabaseService

class FileService:
    
    @staticmethod
    def ensure_cookies_available():
        """Garante que o arquivo de cookies está disponível para o yt-dlp"""
        try:
            cookie_file = DatabaseService.get_cookie_file()
            if cookie_file:
                cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
                # Sempre reescreve o arquivo para garantir que está atualizado
                with open(cookies_path, 'wb') as f:
                    f.write(cookie_file.content)
                logging.info(f"Arquivo de cookies escrito em: {cookies_path}")
                return True
            else:
                # Remove arquivo se não há cookies no banco
                cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
                if os.path.exists(cookies_path):
                    os.remove(cookies_path)
                    logging.info("Arquivo de cookies removido (não há cookies no banco)")
            return False
        except Exception as e:
            logging.error(f"Erro ao escrever arquivo de cookies: {e}")
            return False

    @staticmethod
    def check_cookie_status():
        """Verifica se o arquivo de cookies está sincronizado"""
        try:
            cookie_file = DatabaseService.get_cookie_file()
            cookies_path = os.path.join(os.getcwd(), 'cookies.txt')
            
            if cookie_file and not os.path.exists(cookies_path):
                return 'needs_sync'
            elif not cookie_file and os.path.exists(cookies_path):
                return 'orphaned_file'
            return 'ok'
        except:
            return 'error'