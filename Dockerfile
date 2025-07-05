# Usa buildx para criar uma imagem multiplataforma
FROM --platform=$BUILDPLATFORM python:3.9-bullseye

# Instala o ffmpeg, dependência para o pydub (conversão de áudio)
RUN apt-get update && apt-get install -y ffmpeg --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expõe uma porta interna padrão. A porta externa será mapeada no docker-compose.
EXPOSE 5000

# Executa a aplicação diretamente com o formato JSON, que é mais robusto para multi-arquitetura.
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
