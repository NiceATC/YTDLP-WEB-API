from .auth_routes import auth_bp
from .admin_routes import admin_bp
from .api_routes import api_bp
from .main_routes import main_bp

def register_routes(app):
    """Registra todas as rotas da aplicação"""
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(main_bp)