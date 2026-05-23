"""
Incremental Update Engine Module
Handles atomic file updates with delete-then-insert strategy.
"""

import os
import hashlib
import time
import threading
import sqlite3
from collections import deque
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from logging_config import get_logger
from database_schema import DatabaseManager
from parser_interface import get_parser_for_file, identify_language, ParseResult
from file_monitor_module import FileEvent, FileEventType

logger = get_logger(__name__)

# Auto-import built-in parsers so they register themselves.
# Without this, process_file_event would fail with "No parser available"
# if the caller hasn't explicitly imported the parser modules.
try:
    import python_parser  # noqa: F401
except ImportError:
    pass


@dataclass
class UpdateStatistics:
    """Statistics for an update operation."""
    file_path: str
    event_type: str
    processing_time_ms: float
    types_count: int = 0
    functions_count: int = 0
    calls_count: int = 0
    references_count: int = 0
    success: bool = True
    error_message: Optional[str] = None


class IncrementalUpdateEngine:
    """
    Core engine for incremental code knowledge graph updates.
    Implements delete-then-insert strategy for atomic updates.
    """
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self.stats_history: deque = deque(maxlen=10000)
        self._sync_lock = threading.Lock()
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> Optional[bytes]:
        """Calculate MD5 hash of file content using chunked reading."""
        try:
            md5_hash = hashlib.md5()
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(8192)  # 8KB chunks
                    if not chunk:
                        break
                    md5_hash.update(chunk)
            return md5_hash.digest()
        except Exception:
            return None
    
    @staticmethod
    def calculate_string_hash(content: str) -> bytes:
        """Calculate MD5 hash of string content."""
        return hashlib.md5(content.encode('utf-8')).digest()
    
    def process_file_event(self, event: FileEvent) -> UpdateStatistics:
        """
        Process a file event (create, modify, delete).
        This is the main entry point for file updates.
        Includes retry logic for SQLite locked errors.
        """
        logger.info("Processing event: %s for %s", event.event_type.value, event.file_path)
        start_time = time.time()
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                if event.event_type == FileEventType.DELETED:
                    return self._handle_file_deletion(event.file_path, start_time)
                else:
                    return self._handle_file_update(event.file_path, event.event_type.value, start_time)
            except sqlite3.OperationalError as error:
                if "database is locked" in str(error) and attempt < max_retries - 1:
                    logger.warning("Retry attempt %d for %s (database locked)", attempt + 1, event.file_path)
                    time.sleep(0.05 * (attempt + 1))  # Exponential backoff: 50ms, 100ms
                    continue
                logger.error("Failed to process event %s for %s: %s", event.event_type.value, event.file_path, error)
                processing_time = (time.time() - start_time) * 1000
                stats = UpdateStatistics(
                    file_path=event.file_path,
                    event_type=event.event_type.value,
                    processing_time_ms=processing_time,
                    success=False,
                    error_message=str(error)
                )
                self.stats_history.append(stats)
                return stats
            except Exception as error:
                logger.error("Failed to process event %s for %s: %s", event.event_type.value, event.file_path, error)
                processing_time = (time.time() - start_time) * 1000
                stats = UpdateStatistics(
                    file_path=event.file_path,
                    event_type=event.event_type.value,
                    processing_time_ms=processing_time,
                    success=False,
                    error_message=str(error)
                )
                self.stats_history.append(stats)
                return stats
    
    def _handle_file_deletion(self, file_path: str, start_time: float) -> UpdateStatistics:
        """Handle file deletion - remove all related data."""
        logger.info("Deleting file: %s", file_path)
        # Check if file exists in database first
        file_id = self.db.get_file_id_by_path(file_path)

        if not file_id:
            # File not in database, nothing to do
            logger.debug("File not in database, skipping: %s", file_path)
            processing_time = (time.time() - start_time) * 1000
            stats = UpdateStatistics(
                file_path=file_path,
                event_type='deleted',
                processing_time_ms=processing_time,
                success=True
            )
            self.stats_history.append(stats)
            return stats

        self.db.begin_transaction()

        try:
            # Cascade delete handles related entities
            self.db.delete_file_data(file_id)

            self.db.commit_transaction()

            processing_time = (time.time() - start_time) * 1000

            # Log the change only if the file was actually in the database
            if file_id:
                try:
                    self.db.execute_query(
                        """INSERT INTO change_log (file_path, event_type, processed_at, processing_time_ms)
                           VALUES (?, ?, ?, ?)""",
                        (file_path, 'deleted', int(time.time()), processing_time)
                    )
                except Exception:
                    pass  # Don't fail the operation if logging fails

            logger.info("Deleted file %s (id=%d)", file_path, file_id)
            stats = UpdateStatistics(
                file_path=file_path,
                event_type='deleted',
                processing_time_ms=processing_time,
                success=True
            )
            self.stats_history.append(stats)
            return stats

        except Exception as error:
            self.db.rollback_transaction()
            raise error
    
    def _handle_file_update(self, file_path: str, event_type: str, start_time: float) -> UpdateStatistics:
        """Handle file creation or modification."""
        logger.info("Updating file: %s", file_path)
        # Check if file exists and is readable
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Identify language
        language = identify_language(file_path)
        if not language:
            raise ValueError(f"Unknown language for file: {file_path}")
        logger.debug("Language: %s", language)
        
        # Get parser
        parser = get_parser_for_file(file_path)
        if not parser:
            raise ValueError(f"No parser available for: {file_path}")
        logger.debug("Parser: %s", type(parser).__name__)
        
        # Calculate file hash
        file_hash = self.calculate_file_hash(file_path)
        if not file_hash:
            raise IOError(f"Cannot read file: {file_path}")
        
        # Check if hash changed
        existing_file_id = self.db.get_file_id_by_path(file_path)
        hash_changed = True
        if existing_file_id:
            existing_hash_result = self.db.execute_query(
                "SELECT hash FROM files WHERE id = ?", (existing_file_id,)
            )
            if existing_hash_result and existing_hash_result[0][0] == file_hash:
                hash_changed = False
        logger.debug("Hash changed: %s", hash_changed)

        # Skip processing if hash hasn't changed
        if not hash_changed:
            logger.info("Hash unchanged, skipping file: %s", file_path)
            processing_time = (time.time() - start_time) * 1000
            stats = UpdateStatistics(
                file_path=file_path,
                event_type=event_type,
                processing_time_ms=processing_time,
                success=True
            )
            self.stats_history.append(stats)
            return stats

        # Parse file
        parse_result = parser.parse_file(file_path)
        logger.debug("Found %d types, %d functions, %d calls",
                     len(parse_result.types), len(parse_result.functions), len(parse_result.calls))
        
        # Begin transaction
        self.db.begin_transaction()
        
        try:
            # Step 1: Delete old data if file exists
            if existing_file_id:
                self.db.delete_file_data(existing_file_id)
            
            # Step 2: Insert new file record
            file_id = self._insert_file_record(file_path, language, file_hash)
            
            # Step 3: Insert types and functions
            type_id_map = self._insert_types(parse_result.types, file_id)

            # Extend type_id_map with types from other files for cross-file reference resolution
            cross_file_type_count = 0
            try:
                existing_types = self.db.execute_query(
                    """SELECT name, id FROM types WHERE file_id != ?""",
                    (file_id,)
                )
                for type_name, type_id in existing_types:
                    if type_name not in type_id_map:  # Don't override current file's types
                        type_id_map[type_name] = type_id
                        cross_file_type_count += 1
            except Exception:
                pass
            logger.debug("Cross-file types: %d", cross_file_type_count)

            func_id_map = self._insert_functions(parse_result.functions, file_id, type_id_map, language)

            # Extend func_id_map with functions from other files for cross-file call resolution
            cross_file_func_count = 0
            try:
                existing_funcs = self.db.execute_query(
                    """SELECT f.name, f.type_id, t.name as type_name, f.id
                       FROM functions f
                       LEFT JOIN types t ON f.type_id = t.id
                       WHERE f.file_id != ?""",
                    (file_id,)
                )
                for func_name, type_id, type_name, func_id in existing_funcs:
                    key = f"{type_name or '__module__'}.{func_name}"
                    if key not in func_id_map:  # Don't override current file's functions
                        func_id_map[key] = func_id
                        cross_file_func_count += 1
            except Exception:
                pass  # Non-critical: cross-file resolution is best-effort
            logger.debug("Cross-file functions: %d", cross_file_func_count)
            
            # Step 4: Insert relationships
            self._insert_calls(parse_result.calls, file_id, func_id_map, type_id_map)
            self._insert_references(parse_result.references, file_id, type_id_map)
            
            # Commit transaction
            self.db.commit_transaction()

            # Record statistics
            processing_time = (time.time() - start_time) * 1000

            # Log the change
            try:
                self.db.execute_query(
                    """INSERT INTO change_log (file_path, event_type, processed_at, processing_time_ms)
                       VALUES (?, ?, ?, ?)""",
                    (file_path, event_type, int(time.time()), processing_time)
                )
            except Exception:
                pass  # Don't fail the operation if logging fails

            logger.info("Successfully updated file: %s (%d types, %d functions, %d calls)",
                        file_path, len(parse_result.types), len(parse_result.functions), len(parse_result.calls))
            stats = UpdateStatistics(
                file_path=file_path,
                event_type=event_type,
                processing_time_ms=processing_time,
                types_count=len(parse_result.types),
                functions_count=len(parse_result.functions),
                calls_count=len(parse_result.calls),
                references_count=len(parse_result.references),
                success=True
            )
            self.stats_history.append(stats)
            return stats
            
        except Exception as error:
            self.db.rollback_transaction()
            raise error
    
    def _insert_file_record(self, file_path: str, language: str, file_hash: bytes) -> int:
        """Insert a file record and return its ID."""
        cursor = self.db.connection.cursor()
        cursor.execute(
            """INSERT INTO files (path, language, hash, modified) 
               VALUES (?, ?, ?, ?)""",
            (file_path, language, file_hash, int(time.time()))
        )
        file_id = cursor.lastrowid
        logger.debug("Inserted file record with id=%d", file_id)
        return file_id
    
    def _insert_types(self, types: List[Any], file_id: int) -> Dict[str, int]:
        """Insert type records and return name-to-ID mapping."""
        type_id_map = {}
        cursor = self.db.connection.cursor()
        
        for type_info in types:
            cursor.execute(
                """INSERT INTO types (name, file_id, kind, flags, line_start, line_end)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (type_info.name, file_id, type_info.kind, type_info.flags,
                 type_info.line_start, type_info.line_end)
            )
            type_id = cursor.lastrowid
            type_id_map[type_info.name] = type_id
        
        logger.debug("Inserted %d types", len(types))
        return type_id_map
    
    def _insert_functions(self, functions: List[Any], file_id: int, 
                          type_id_map: Dict[str, int], language: str = 'python') -> Dict[str, int]:
        """Insert function records and return name-to-ID mapping."""
        func_id_map = {}
        cursor = self.db.connection.cursor()
        
        for func_info in functions:
            type_id = None
            if func_info.type_name and func_info.type_name in type_id_map:
                type_id = type_id_map[func_info.type_name]
            
            cursor.execute(
                """INSERT INTO functions (name, type_id, file_id, language, signature, line_start, line_end)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (func_info.name, type_id, file_id, language, func_info.signature,
                 func_info.line_start, func_info.line_end)
            )
            func_id = cursor.lastrowid
            
            # Create unique key for function lookup
            key = f"{func_info.type_name or '__module__'}.{func_info.name}"
            func_id_map[key] = func_id
        
        logger.debug("Inserted %d functions", len(functions))
        return func_id_map
    
    def _insert_calls(self, calls: List[Any], file_id: int, func_id_map: Dict[str, int],
                      type_id_map: Optional[Dict[str, int]] = None):
        """Insert call relationships.
        
        When a callee is not found in func_id_map (e.g., class instantiation MyClass()),
        falls back to type_id_map to record the call.
        """
        cursor = self.db.connection.cursor()
        inserted = 0
        skipped = 0

        for call_info in calls:
            caller_key = f"{call_info.caller_type or '__module__'}.{call_info.caller_name}"
            callee_key = f"{call_info.callee_type or '__module__'}.{call_info.callee_name}"

            caller_id = func_id_map.get(caller_key)
            callee_id = func_id_map.get(callee_key)

            # Fallback: callee may be a type (class instantiation like MyClass())
            if not callee_id and type_id_map:
                callee_id = type_id_map.get(call_info.callee_name)

            if caller_id and callee_id:
                cursor.execute(
                    """INSERT OR IGNORE INTO calls (caller_id, callee_id, file_id, line_number)
                       VALUES (?, ?, ?, ?)""",
                    (caller_id, callee_id, file_id, call_info.line_number)
                )
                inserted += 1
            else:
                skipped += 1

        logger.debug("Inserted %d calls, %d skipped (no callee found)", inserted, skipped)
    
    def _insert_references(self, references: List[Any], file_id: int, type_id_map: Dict[str, int]):
        """Insert reference relationships."""
        cursor = self.db.connection.cursor()
        inserted = 0
        
        for ref_info in references:
            from_id = type_id_map.get(ref_info.from_name)
            to_id = type_id_map.get(ref_info.to_name)
            
            if from_id and to_id:
                cursor.execute(
                    """INSERT OR IGNORE INTO relationships (from_id, to_id, kind, file_id, line_number)
                       VALUES (?, ?, ?, ?, ?)""",
                    (from_id, to_id, ref_info.ref_kind, file_id, ref_info.line_number)
                )
                inserted += 1
        
        logger.debug("Inserted %d references", inserted)
    
    def perform_full_sync(self, project_path: str) -> Dict[str, Any]:
        """
        Perform a full synchronization of the project.
        Scans all files, compares hashes, and updates changed files.
        """
        logger.info("Starting full sync for %s", project_path)
        with self._sync_lock:
            # Ensure WAL data is merged before sync to handle crash recovery.
            # After a SIGKILL, the WAL file may contain uncommitted pages
            # that need to be checkpointed so stale data does not persist.
            try:
                self.db.execute_query("PRAGMA wal_checkpoint(FULL)")
            except Exception:
                pass

            # Run integrity check to detect any corruption from prior crashes
            try:
                integrity_result = self.db.execute_query("PRAGMA integrity_check")
                if integrity_result and integrity_result[0][0] != 'ok':
                    print(f"Database integrity check warning: {integrity_result[0][0]}")
            except Exception:
                pass

            return self._perform_full_sync_impl(project_path)
    
    def _perform_full_sync_impl(self, project_path: str) -> Dict[str, Any]:
        """Internal implementation of full synchronization (called under lock)."""
        start_time = time.time()
        
        # Get all code files
        code_files = self._scan_project_files(project_path)
        
        # Get current file hashes from database
        current_files = self.db.execute_query(
            "SELECT path, hash FROM files"
        )
        db_file_hashes = {row[0]: row[1] for row in current_files}
        
        # Determine changes
        files_to_update = []
        files_to_delete = []
        errors = []
        
        scanned_paths = set()
        
        for file_path in code_files:
            scanned_paths.add(file_path)
            current_hash = self.calculate_file_hash(file_path)
            
            # Skip files that cannot be read (hash is None)
            if current_hash is None:
                errors.append(f"{file_path}: unable to read file (hash calculation failed)")
                continue
            
            if file_path in db_file_hashes:
                if current_hash != db_file_hashes[file_path]:
                    files_to_update.append(file_path)
            else:
                files_to_update.append(file_path)
        
        # Find deleted files
        for db_path in db_file_hashes:
            if db_path not in scanned_paths:
                files_to_delete.append(db_path)
        
        # Process updates
        updated_count = 0
        deleted_count = 0
        
        for file_path in files_to_update:
            try:
                # Use CREATED for new files, MODIFIED for existing files
                if file_path in db_file_hashes:
                    event_type = FileEventType.MODIFIED
                else:
                    event_type = FileEventType.CREATED
                event = FileEvent(
                    file_path=file_path,
                    event_type=event_type,
                    timestamp=time.time()
                )
                result = self.process_file_event(event)
                if result.success:
                    updated_count += 1
                else:
                    errors.append(f"{file_path}: {result.error_message}")
            except Exception as error:
                errors.append(f"{file_path}: {error}")
        
        for file_path in files_to_delete:
            try:
                event = FileEvent(
                    file_path=file_path,
                    event_type=FileEventType.DELETED,
                    timestamp=time.time()
                )
                result = self.process_file_event(event)
                if result.success:
                    deleted_count += 1
                else:
                    errors.append(f"{file_path}: {result.error_message}")
            except Exception as error:
                errors.append(f"{file_path}: {error}")
        
        total_time = time.time() - start_time
        
        logger.info(
            "Full sync completed: %d updated, %d deleted, %d unchanged, %d errors in %.2fs",
            updated_count, deleted_count, len(code_files) - updated_count, len(errors), total_time
        )

        return {
            'total_time_seconds': total_time,
            'files_updated': updated_count,
            'files_deleted': deleted_count,
            'files_unchanged': len(code_files) - updated_count,
            'errors': errors
        }
    
    def _scan_project_files(self, project_path: str) -> List[str]:
        """Scan project directory for code files."""
        code_files = []
        supported_extensions = {
            '.py', '.pyw', '.java', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs',
            '.c', '.h', '.cpp', '.hpp', '.cs', '.php', '.rb', '.swift',
            '.kt', '.scala', '.dart', '.lua'
        }
        
        skip_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', 
                     'dist', 'build', '.idea', '.vscode'}
        
        for root, dirs, files in os.walk(project_path):
            # Skip hidden and common non-code directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in skip_dirs]
            
            for filename in files:
                # Skip hidden files (starting with .)
                if filename.startswith('.'):
                    continue
                ext = os.path.splitext(filename)[1].lower()
                if ext in supported_extensions:
                    file_path = os.path.join(root, filename)
                    code_files.append(file_path)
        
        logger.debug("Scanning %s, found %d code files", project_path, len(code_files))
        return code_files
    
    def get_recent_statistics(self, count: int = 10) -> List[UpdateStatistics]:
        """Get recent update statistics."""
        if not self.stats_history:
            return []
        # Convert to list for slicing (deque doesn't support slice)
        return list(self.stats_history)[-count:]
    
    def clear_statistics(self):
        """Clear statistics history."""
        self.stats_history.clear()


if __name__ == '__main__':
    import sys
    
    # Test the engine
    db_path = '/data/user/work/code_knowledge_graph_system/data/test.db'
    project_path = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    from database_schema import create_database
    
    create_database(db_path)
    
    with DatabaseManager(db_path) as db_manager:
        engine = IncrementalUpdateEngine(db_manager)
        
        print(f"Performing full sync of {project_path}...")
        result = engine.perform_full_sync(project_path)
        
        print(f"\nSync complete:")
        print(f"  Time: {result['total_time_seconds']:.2f}s")
        print(f"  Updated: {result['files_updated']}")
        print(f"  Deleted: {result['files_deleted']}")
        print(f"  Unchanged: {result['files_unchanged']}")
        
        if result['errors']:
            print(f"\nErrors ({len(result['errors'])}):")
            for error in result['errors'][:5]:
                print(f"  - {error}")
