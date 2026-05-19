"""
Database Schema Module
Defines the SQLite database schema for the code knowledge graph system.
All tables use integer primary keys for optimal performance.
"""

import sqlite3
import os
import threading


# SQL statements for creating tables
CREATE_TABLES_SQL = """
-- Files table: stores all code files with their metadata
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    language TEXT NOT NULL,
    hash BLOB NOT NULL,
    modified INTEGER NOT NULL
);

-- Create index on path for fast lookups
CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);

-- Types table: stores classes, interfaces, structs, enums
CREATE TABLE IF NOT EXISTS types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    file_id INTEGER NOT NULL,
    kind TEXT NOT NULL,  -- class, interface, struct, enum, function
    flags INTEGER DEFAULT 0,  -- generic flags for extensibility
    line_start INTEGER DEFAULT 0,
    line_end INTEGER DEFAULT 0,
    UNIQUE(name, file_id),
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_types_file_id ON types(file_id);
CREATE INDEX IF NOT EXISTS idx_types_name ON types(name);
CREATE INDEX IF NOT EXISTS idx_types_kind ON types(kind);

-- Functions table: stores methods and standalone functions
CREATE TABLE IF NOT EXISTS functions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type_id INTEGER,  -- NULL for standalone functions
    file_id INTEGER NOT NULL,
    language TEXT NOT NULL,
    signature TEXT,
    line_start INTEGER DEFAULT 0,
    line_end INTEGER DEFAULT 0,
    UNIQUE(name, type_id, file_id),
    FOREIGN KEY (type_id) REFERENCES types(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_functions_type_id ON functions(type_id);
CREATE INDEX IF NOT EXISTS idx_functions_file_id ON functions(file_id);
CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(name);

-- Calls table: stores function call relationships
CREATE TABLE IF NOT EXISTS calls (
    caller_id INTEGER NOT NULL,
    callee_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL,
    line_number INTEGER DEFAULT 0,
    PRIMARY KEY (caller_id, callee_id, file_id, line_number),
    FOREIGN KEY (caller_id) REFERENCES functions(id) ON DELETE CASCADE,
    FOREIGN KEY (callee_id) REFERENCES functions(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_id);
CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_id);

-- Relationships table: stores inheritance, implementation, import relationships
CREATE TABLE IF NOT EXISTS relationships (
    from_id INTEGER NOT NULL,
    to_id INTEGER NOT NULL,
    kind TEXT NOT NULL,  -- inherit, implement, import, use
    file_id INTEGER NOT NULL,
    line_number INTEGER DEFAULT 0,
    PRIMARY KEY (from_id, to_id, kind, file_id),
    FOREIGN KEY (from_id) REFERENCES types(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES types(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_rels_from ON relationships(from_id);
CREATE INDEX IF NOT EXISTS idx_rels_to ON relationships(to_id);
CREATE INDEX IF NOT EXISTS idx_rels_kind ON relationships(kind);

-- Statistics table: stores system metrics
CREATE TABLE IF NOT EXISTS statistics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT UNIQUE NOT NULL,
    metric_value INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);

-- Change log table: tracks file changes for debugging
CREATE TABLE IF NOT EXISTS change_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- created, modified, deleted
    processed_at INTEGER NOT NULL,
    processing_time_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_changelog_time ON change_log(processed_at);
"""


class DatabaseManager:
    """Manages SQLite database connections and operations.
    
    Thread-safe implementation using connection-per-thread pattern.
    """
    
    def __init__(self, database_path):
        """Initialize database manager with the given database path."""
        self.database_path = database_path
        self._local = threading.local()
        self._all_connections = set()
        self._connections_lock = threading.Lock()
        self._closed = False
        self._ensure_directory_exists()
    
    def _ensure_directory_exists(self):
        """Ensure the directory for the database file exists."""
        directory = os.path.dirname(self.database_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    
    def _get_connection(self):
        """Get thread-local database connection."""
        if self._closed:
            raise RuntimeError("DatabaseManager has been closed")
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(self.database_path, timeout=30)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA busy_timeout = 30000")  # 30s busy timeout
            with self._connections_lock:
                self._all_connections.add(conn)
            self._local.connection = conn
            self._local.in_transaction = False
        return self._local.connection
    
    @property
    def connection(self):
        """Get current thread's connection."""
        return self._get_connection()
    
    def connect(self):
        """Establish database connection for current thread."""
        return self._get_connection()
    
    def close(self):
        """Close the current thread's database connection."""
        if hasattr(self._local, 'connection') and self._local.connection:
            conn = self._local.connection
            with self._connections_lock:
                self._all_connections.discard(conn)
            conn.close()
            self._local.connection = None
            self._local.in_transaction = False
    
    def close_all(self):
        """Close all database connections across all threads."""
        with self._connections_lock:
            for conn in list(self._all_connections):
                try:
                    conn.close()
                except Exception:
                    pass
            self._all_connections.clear()
        self._closed = True
        # Also clear thread-local reference
        if hasattr(self._local, 'connection'):
            self._local.connection = None
    
    def initialize_schema(self):
        """Create all tables and indexes."""
        conn = self._get_connection()
        conn.executescript(CREATE_TABLES_SQL)
        conn.commit()
    
    def begin_transaction(self):
        """Begin a new explicit transaction."""
        conn = self._get_connection()
        conn.execute("BEGIN TRANSACTION")
        self._local.in_transaction = True
    
    def commit_transaction(self):
        """Commit current transaction."""
        self._get_connection().commit()
        self._local.in_transaction = False
    
    def rollback_transaction(self):
        """Rollback current transaction."""
        self._get_connection().rollback()
        self._local.in_transaction = False
    
    @staticmethod
    def _is_write_query(query):
        """Check if a query modifies data (INSERT, UPDATE, DELETE, REPLACE, DROP, CREATE, ALTER)."""
        stripped = query.strip().upper()
        write_prefixes = (
            'INSERT', 'UPDATE', 'DELETE', 'REPLACE',
            'DROP', 'CREATE', 'ALTER', 'PRAGMA',
        )
        return any(stripped.startswith(prefix) for prefix in write_prefixes)
    
    def execute_query(self, query, parameters=None):
        """Execute a query and return results.
        
        For write operations (INSERT, UPDATE, DELETE, etc.), automatically commits
        if not inside an explicit transaction, preventing data loss from concurrent
        threads that each have their own connection.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        if parameters:
            cursor.execute(query, parameters)
        else:
            cursor.execute(query)
        
        # Auto-commit write operations when not in an explicit transaction.
        # This prevents data loss when multiple threads perform writes
        # through execute_query without manually calling commit_transaction().
        if not self._local.in_transaction and self._is_write_query(query):
            conn.commit()
        
        return cursor.fetchall()
    
    def execute_many(self, query, parameters_list):
        """Execute a query with multiple parameter sets.
        
        Automatically commits if not inside an explicit transaction.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, parameters_list)
        
        # Auto-commit write operations when not in an explicit transaction.
        if not self._local.in_transaction and self._is_write_query(query):
            conn.commit()
    
    def get_file_id_by_path(self, file_path):
        """Get file ID by its path."""
        result = self.execute_query(
            "SELECT id FROM files WHERE path = ?",
            (file_path,)
        )
        return result[0][0] if result else None
    
    def delete_file_data(self, file_id):
        """Delete all data related to a file (cascade delete handles relations)."""
        self.execute_query("DELETE FROM files WHERE id = ?", (file_id,))
    
    def get_statistics(self):
        """Get database statistics."""
        stats = {}
        tables = ['files', 'types', 'functions', 'calls', 'relationships']
        for table in tables:
            result = self.execute_query(f"SELECT COUNT(*) FROM {table}")
            stats[table] = result[0][0] if result else 0
        return stats
    
    def get_file_statistics(self):
        """Get file count by language."""
        result = self.execute_query(
            "SELECT language, COUNT(*) FROM files GROUP BY language"
        )
        return {row[0]: row[1] for row in result}
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def create_database(database_path):
    """Create a new database with the complete schema."""
    with DatabaseManager(database_path) as db_manager:
        db_manager.initialize_schema()
        print(f"Database initialized at: {database_path}")
        return db_manager


if __name__ == '__main__':
    db_path = '/data/user/work/code_knowledge_graph_system/data/code_knowledge.db'
    create_database(db_path)
