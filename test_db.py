import psycopg2
from config import Config

try:
    conn = psycopg2.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        sslmode='require'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = cursor.fetchall()
    print("Connection successful! Tables in the database:")
    for table in tables:
        print(table[0])
    cursor.close()
    conn.close()
except Exception as e:
    print("Connection failed!")
    print(e)
