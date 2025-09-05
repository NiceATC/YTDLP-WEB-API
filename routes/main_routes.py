from flask import Blueprint, render_template
from services.database_service import DatabaseService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def documentation():
    # Get app settings for white label
    app_settings = DatabaseService.get_app_settings()
    
    # Get public download limit
    public_download_limit = DatabaseService.get_setting('PUBLIC_DOWNLOAD_LIMIT', 5)
    
    return render_template('docs/documentation.html', 
                         app_settings=app_settings,
                         public_download_limit=public_download_limit)