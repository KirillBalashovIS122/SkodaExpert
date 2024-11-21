class Config:
    SQLALCHEMY_DATABASE_URI = 'firebird+fdb://sysdba:masterkey@localhost:3050/D:/rdb/SKODA_EXPERT.fdb?charset=UTF8'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'ваш_секретный_ключ'

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig
}
