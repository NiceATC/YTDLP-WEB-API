import os
import logging
import requests
import http.cookiejar
from services.database_service import DatabaseService


class FileService:
    @staticmethod
    def ensure_cookies_available():
        """Garante que o arquivo de cookies está disponível para o yt-dlp"""
        try:
            cookie_file = DatabaseService.get_cookie_file()
            cookies_path = os.path.join(os.getcwd(), "cookies.txt")

            if cookie_file:
                # Sempre reescreve o arquivo para garantir que está atualizado
                with open(cookies_path, "wb") as f:
                    f.write(cookie_file.content)
                logging.info(f"Arquivo de cookies escrito em: {cookies_path}")
                return True
            else:
                # Remove o arquivo se não há cookies no banco
                if os.path.exists(cookies_path):
                    os.remove(cookies_path)
                    logging.info("Arquivo de cookies removido (não há cookies no banco)")
                return False
        except Exception as e:
            logging.error(f"Erro ao escrever arquivo de cookies: {e}")
            return False

    @staticmethod
    def check_cookie_status():
        """Verifica se o arquivo de cookies está sincronizado e ainda é válido no YouTube"""
        try:
            cookie_file = DatabaseService.get_cookie_file()
            cookies_path = os.path.join(os.getcwd(), "cookies.txt")

            if cookie_file and not os.path.exists(cookies_path):
                return "needs_sync"
            elif not cookie_file and os.path.exists(cookies_path):
                return "orphaned_file"
            elif cookie_file and os.path.exists(cookies_path):
                # Verifica validade do cookie com o YouTube
                try:
                    cj = http.cookiejar.MozillaCookieJar()
                    cj.load(cookies_path, ignore_discard=True, ignore_expires=True)
                    cookies_dict = {cookie.name: cookie.value for cookie in cj}

                    response = requests.get(
                        "https://www.youtube.com/feed/subscriptions",
                        cookies=cookies_dict,
                        allow_redirects=False,
                        timeout=10,
                    )

                    if response.status_code in [302, 303] and "accounts.google.com" in response.headers.get("Location", ""):
                        return "expired"
                    if "Sign in" in response.text or "Faça login" in response.text:
                        return "expired"

                    return "ok"
                except:
                    return "expired"

            # Se nem cookie_file nem o arquivo físico existem
            if not cookie_file and not os.path.exists(cookies_path):
                return "missing"

            return "ok"
        except:
            return "error"
