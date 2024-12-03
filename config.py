class Config:
    SQLALCHEMY_DATABASE_URI = 'firebird+fdb://sysdba:masterkey@localhost:3050/D:/rdb/SKODA_EXPERT.FDB?charset=UTF8'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'my_secret_key'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}