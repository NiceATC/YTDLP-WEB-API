# YTDL Web API 🎥🎧

Uma API REST em Flask + Celery + yt-dlp para baixar vídeos ou áudios do YouTube (ou outros sites suportados) com controle de usuários, sistema de API keys, autenticação via cookies e painel de administração.

---

## ✨ Funcionalidades

✅ Download de vídeos ou áudios em MP4/MP3 usando yt-dlp.  
✅ Painel de administração com login para gerenciar configurações, histórico e API keys.  
✅ Suporte a autenticação por API Key para requisições programáticas.  
✅ Cookies persistentes para login em plataformas que exigem autenticação.  
✅ Sistema de filas com Celery para processar downloads de forma assíncrona.  
✅ Persistência em banco de dados PostgreSQL.  
✅ Pronto para produção com Docker + Traefik + Swarm.

---

<img width="1910" height="885" alt="image" src="https://github.com/user-attachments/assets/1015c884-204a-4479-90e0-7695daf25006" />


## 🚀 Como usar

### 1️⃣ Clone o repositório

```bash
git clone https://github.com/NiceATC/YTDLP-WEB-API.git
cd ytdl-web-api
```

### 2️⃣ Configure variáveis de ambiente
Crie um arquivo .env ou defina estas variáveis no ambiente:

```bash
BASE_URL=http://seu-dominio-ou-ip:5000
REDIS_URL=redis://redis:6379
DATABASE_URL=postgresql://usuario:senha@postgres:5432/ytdl-web-api
SECRET_KEY=sua-chave-secreta
DEFAULT_PASSWORD=admin
```

### 3️⃣ Suba com Docker
Com Docker Compose ou Docker Swarm:

```bash
docker stack deploy -c docker-compose.yml ytdl
```

Ou, se não usa Swarm:

```bash
docker-compose up -d
```

Se preferir pode usar o [DOCKER HUB](https://hub.docker.com/r/niceatc/ytdl-web-api)

### 4️⃣ Acesse o painel administrativo
Abra no navegador:

```bash
http://seu-dominio-ou-ip:5000/login
```
Login padrão: senha definida em DEFAULT_PASSWORD ou admin se não configurado.

No primeiro acesso, será solicitado que você altere a senha.

⚙️ API endpoints
Healthcheck

```bash
GET /api/health
```
Retorna o status dos serviços Redis, Database e cookies.

Iniciar download
```yaml
GET /api/media
Headers: X-API-Key: SUA_API_KEY
Query params:
  - type: audio | video
  - url: URL do vídeo
  - quality: opcional, ex.: 720p
  - bitrate: opcional, ex.: 192
```
Retorna status da tarefa ou resultado imediato.

Verificar status de tarefa
```vbnet
GET /api/tasks/<task_id>
Headers: X-API-Key: SUA_API_KEY
```
Retorna o status e o resultado de uma tarefa em processamento.

Download do arquivo gerado
```bash
GET /api/download/<filename>
```
Serve o arquivo final (MP4/MP3) para download.

### 🗂️ Estrutura dos serviços
yt-app: servidor Flask com o painel e as rotas de API.

yt-worker: Celery worker processando os downloads de forma assíncrona.

postgres: banco de dados para persistir usuários, histórico e configurações.

redis: backend de filas para Celery e rate limiting.

### 🐳 Volumes importantes
ytdlp_data → compartilhado entre yt-app e yt-worker, armazena os arquivos baixados persistentes em /app/downloads.

### 🔐 Autenticação & Segurança
Use cookies atualizados para baixar vídeos privados ou restritos (menu de upload no painel).

Gere API Keys no painel para autorizar chamadas à API.

Configure HTTPS via Traefik (ou outro proxy reverso) para proteger suas requisições.

### 🔎 Tecnologias
Python 3.9

Flask

Celery

yt-dlp

PostgreSQL

Redis

Docker & Docker Swarm

Traefik (opcional, mas recomendado)

### 📄 Licença
MIT. Faça bom uso e contribua!

### 🙌 Créditos e Referência
Este projeto foi desenvolvido com IA logo erros e falhas são esperados, mas espero que ajude!


 - [YTDLP-API](https://github.com/Dot-ser/YTDLP-API) (Pela Ideia Orginal)

---
