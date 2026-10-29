import sqlite3

DATABASE = 'database.db'

def get_db():
    from flask import g
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # Enables dictionary-style column access
        db.execute("PRAGMA foreign_keys = ON;")
    return db

def init_db(app):
    with app.app_context():
        db = get_db()
        with open('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

def close_connection(exception):
    from flask import g
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
