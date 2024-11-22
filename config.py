class Config:
    SQLALCHEMY_DATABASE_URI = 'firebird+fdb://sysdba:masterkey@localhost:3050/D:/rdb/SE_CAR_SERVICE.FDB?charset=UTF8'
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