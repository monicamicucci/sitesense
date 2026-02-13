import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", "root"),
            database=os.getenv("MYSQL_DATABASE", "Initalya"),
            charset="utf8mb4",
            use_unicode=True,
        )
        try:
            # Imposta charset/collation a livello di sessione per massima compatibilità
            conn.set_charset_collation("utf8mb4", "utf8mb4_unicode_ci")
        except Exception:
            try:
                cur = conn.cursor()
                cur.execute("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci")
                cur.close()
            except Exception:
                pass
        return conn
    except Error as e:
        print("Errore connessione MySQL:", e)
        return None

if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("✅ Connesso a MySQL")
        conn.close()
