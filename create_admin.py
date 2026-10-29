import sqlite3
import sys
from werkzeug.security import generate_password_hash

DATABASE = 'database.db'

def create_admin(username, email, password):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    hashed_pw = generate_password_hash(password)
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, is_verified, role) VALUES (?, ?, ?, 1, 'admin')",
            (username, email, hashed_pw)
        )
        conn.commit()
        print(f"Admin account '{username}' created successfully!")
    except sqlite3.IntegrityError:
        print(f"User '{username}' or email '{email}' already exists.")
    finally:
        conn.close()

if __name__ == '__main__':
    u = input("Admin Username [admin]: ").strip() or "admin"
    e = input("Admin Email [admin@example.com]: ").strip() or "admin@example.com"
    p = input("Admin Password [admin123]: ").strip() or "admin123"
    create_admin(u, e, p)
