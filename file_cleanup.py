import os
import time
from config import Config

def cleanup_old_files():
    folder = Config.DOWNLOAD_FOLDER
    if not os.path.isdir(folder):
        print(f"Diretório não encontrado: {folder}")
        return

    cutoff = time.time() - Config.CLEANUP_OLDER_THAN_SECONDS

    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            if os.path.getmtime(file_path) < cutoff:
                print(f"Removendo arquivo antigo: {filename}")
                os.remove(file_path)

if __name__ == "__main__":
    print("Iniciando limpeza de arquivos antigos...")
    cleanup_old_files()
    print("Limpeza concluída.")