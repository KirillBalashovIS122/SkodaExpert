from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
import logging

db = SQLAlchemy()
csrf = CSRFProtect()

def create_app():
    print("Hello")
    app = Flask(__name__)
    app.config.from_object('config.DevelopmentConfig')

    db.init_app(app)
    csrf.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    logging.basicConfig(level=logging.DEBUG)
    return app