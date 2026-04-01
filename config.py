import os

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    uri = os.environ.get("DATABASE_URL")

    if uri and uri.startswith("mysql://"):
        uri = uri.replace("mysql://", "mysql+pymysql://", 1)

    SQLALCHEMY_DATABASE_URI = uri