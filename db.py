import mysql.connector
from flask import g
from config import Config

# This function will now get the connection from the request context 'g'
# or create it if it doesn't exist for the current request.
def get_db_connection():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
    return g.db
import mysql.connector
from flask import g
from config import Config

# This function will now get the connection from the request context 'g'
# or create it if it doesn't exist for the current request.
def get_db_connection():
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
    return g.db

# This function will be called from app.py to close the connection
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()