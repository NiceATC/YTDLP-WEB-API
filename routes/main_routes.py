from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def documentation():
    return render_template('docs/documentation.html')