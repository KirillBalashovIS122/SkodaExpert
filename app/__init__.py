"""
Инициализация приложения Flask.

Этот файл содержит функцию для создания и настройки приложения Flask,
а также инициализацию базы данных и CSRF-защиты.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()

def create_app():
    """
    Создает и настраивает приложение Flask.

    Returns:
        Flask: Настроенное приложение Flask.
    """
    app = Flask(__name__)
    app.config.from_object('config.DevelopmentConfig')

    db.init_app(app)
    csrf.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    return app
