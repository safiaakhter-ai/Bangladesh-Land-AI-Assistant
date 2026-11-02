import sqlite3
import json
import uuid
import os
from datetime import datetime

DB_PATH = os.environ.get('LAND_CHAT_DB', os.path.join(os.path.dirname(__file__), 'data', 'chat_history.db'))

def get_db_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=10000')
    conn.row_factory = sqlite3.Row
    return conn

def init_chat_db():
    """Initialize SQLite tables for storing chat sessions and messages persistently."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Chat Sessions Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Chat Messages Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_messages (
                message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()

def create_session(title="নতুন তথ্য অনুসন্ধান"):
    """Create a new chat session thread."""
    init_chat_db()
    session_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chat_sessions (session_id, title)
            VALUES (?, ?)
        ''', (session_id, title))
        conn.commit()
    return session_id

def get_all_sessions():
    """Fetch all chat sessions ordered by newest updated first."""
    init_chat_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT session_id, title, created_at, updated_at
            FROM chat_sessions
            ORDER BY updated_at DESC
        ''')
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_session_messages(session_id):
    """Retrieve full message history for a given session ID."""
    init_chat_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT message_id, session_id, sender, content, metadata_json, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY message_id ASC
        ''', (session_id,))
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            item = dict(row)
            if item.get('metadata_json'):
                try:
                    item['metadata'] = json.loads(item['metadata_json'])
                except:
                    item['metadata'] = None
            else:
                item['metadata'] = None
            result.append(item)
        return result

def add_message(session_id, sender, content, metadata=None):
    """Add a message to a session thread and update session timestamp."""
    init_chat_db()
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Verify session exists, if not create it
        cursor.execute("SELECT session_id, title FROM chat_sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        
        title_summary = content[:35] + ("..." if len(content) > 35 else "")
        if not row:
            cursor.execute("INSERT INTO chat_sessions (session_id, title) VALUES (?, ?)", (session_id, title_summary))
        elif sender == 'user' and (row[1] == "নতুন তথ্য অনুসন্ধান" or row[1] == "New Search"):
            cursor.execute("UPDATE chat_sessions SET title = ? WHERE session_id = ?", (title_summary, session_id))
            
        cursor.execute('''
            INSERT INTO chat_messages (session_id, sender, content, metadata_json)
            VALUES (?, ?, ?, ?)
        ''', (session_id, sender, content, metadata_json))
        
        cursor.execute('''
            UPDATE chat_sessions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
        ''', (session_id,))
        
        conn.commit()

def delete_session(session_id):
    """Delete a chat session and all its messages."""
    init_chat_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        conn.commit()

def update_session_title(session_id, title):
    """Update title of a chat session."""
    init_chat_db()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?", (title, session_id))
        conn.commit()

if __name__ == "__main__":
    init_chat_db()
    print("Chat history database initialized successfully.")
