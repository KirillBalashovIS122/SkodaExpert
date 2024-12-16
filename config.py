"""
Конфигурация приложения.

Этот файл содержит базовые настройки приложения, включая конфигурацию базы данных,
ключи безопасности и режимы работы (разработка/производство).
"""

class Config:
    """Базовый класс конфигурации."""
    SQLALCHEMY_DATABASE_URI = 'firebird+fdb://sysdba:masterkey@localhost:3050/D:/rdb/SKODA_EXPERT.FDB?charset=UTF8'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'my_secret_key'

class DevelopmentConfig(Config):
    """Конфигурация для режима разработки."""
    DEBUG = True

class ProductionConfig(Config):
    """Конфигурация для режима производства."""
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}
