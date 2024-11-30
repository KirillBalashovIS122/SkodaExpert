from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
import logging

db = SQLAlchemy()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.DevelopmentConfig')

    db.init_app(app)
    csrf.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    # Настройка логирования
    logging.basicConfig(level=logging.DEBUG)
    file_handler = logging.FileHandler('app.log')
    file_handler.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)

    return app