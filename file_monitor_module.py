"""
File Monitor Module
Cross-platform file monitoring with debouncing and event merging.
Uses watchdog library for efficient file system monitoring.
"""

import os
import time
import threading
from queue import Queue, Empty
from typing import Callable, Set, Dict, Optional
from dataclasses import dataclass
from enum import Enum

# Try to import watchdog, provide fallback if not available
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class FileEventType(Enum):
    """Enumeration of file event types."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class FileEvent:
    """Represents a file system event."""
    file_path: str
    event_type: FileEventType
    timestamp: float
    
    def __hash__(self):
        return hash((self.file_path, self.event_type))
    
    def __eq__(self, other):
        if isinstance(other, FileEvent):
            return self.file_path == other.file_path and self.event_type == other.event_type
        return False


class DebounceMergeQueue:
    """
    Queue that debounces and merges file events.
    Events for the same file within the debounce window are merged.
    """
    
    def __init__(self, debounce_window_ms: float = 1000.0):
        self.debounce_window = debounce_window_ms / 1000.0  # Convert to seconds
        self.pending_events: Dict[str, FileEvent] = {}
        self.processed_queue: Queue = Queue()
        self.lock = threading.RLock()
        self.timer: Optional[threading.Timer] = None
        self.callback: Optional[Callable[[FileEvent], None]] = None
    
    def set_callback(self, callback: Callable[[FileEvent], None]):
        """Set the callback function for processed events."""
        self.callback = callback
    
    def add_event(self, event: FileEvent):
        """Add an event to the queue with debouncing."""
        with self.lock:
            # Merge with existing event for same file
            if event.file_path in self.pending_events:
                existing = self.pending_events[event.file_path]
                # Upgrade created -> modified if file already being tracked
                if existing.event_type == FileEventType.CREATED and event.event_type == FileEventType.MODIFIED:
                    event.event_type = FileEventType.CREATED  # Keep as created
                # Upgrade to deleted if file is deleted
                elif event.event_type == FileEventType.DELETED:
                    pass  # Keep deleted
            
            self.pending_events[event.file_path] = event
            
            # Reset timer
            if self.timer:
                self.timer.cancel()
            
            self.timer = threading.Timer(self.debounce_window, self._process_pending)
            self.timer.daemon = True
            self.timer.start()
    
    def _process_pending(self):
        """Process all pending events after debounce window."""
        with self.lock:
            events_to_process = list(self.pending_events.values())
            self.pending_events.clear()
        
        for event in events_to_process:
            self.processed_queue.put(event)
            if self.callback:
                try:
                    self.callback(event)
                except Exception as error:
                    print(f"Error processing event callback: {error}")
    
    def get_event(self, timeout: Optional[float] = None) -> Optional[FileEvent]:
        """Get a processed event from the queue."""
        try:
            return self.processed_queue.get(timeout=timeout)
        except Empty:
            return None
    
    def shutdown(self):
        """Shutdown the queue and process remaining events."""
        with self.lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None
            # Collect remaining events and clear pending (inline to avoid reentrant lock)
            events_to_process = list(self.pending_events.values())
            self.pending_events.clear()

        # Dispatch events outside the lock
        for event in events_to_process:
            self.processed_queue.put(event)
            if self.callback:
                try:
                    self.callback(event)
                except Exception as error:
                    print(f"Error processing event callback: {error}")


# Define CodeFileEventHandler only if watchdog is available
if WATCHDOG_AVAILABLE:
    class CodeFileEventHandler(FileSystemEventHandler):
        """Event handler for code file changes."""
        
        def __init__(self, debounce_queue: DebounceMergeQueue, 
                     supported_extensions: Optional[Set[str]] = None):
            self.queue = debounce_queue
            self.supported_extensions = supported_extensions or {
                '.py', '.java', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs',
                '.c', '.h', '.cpp', '.hpp', '.cs', '.php', '.rb', '.swift',
                '.kt', '.scala', '.dart', '.lua'
            }
        
        def _is_code_file(self, file_path: str) -> bool:
            """Check if file is a code file we should track."""
            # Skip hidden files and common non-code directories
            parts = file_path.split(os.sep)
            for part in parts:
                if part.startswith('.') and part not in ('.', '..'):
                    return False
                if part in ('node_modules', '__pycache__', 'venv', '.git', 'dist', 'build'):
                    return False
            
            # Check extension
            ext = os.path.splitext(file_path)[1].lower()
            return ext in self.supported_extensions
        
        def on_modified(self, event):
            if not event.is_directory and self._is_code_file(event.src_path):
                file_event = FileEvent(
                    file_path=event.src_path,
                    event_type=FileEventType.MODIFIED,
                    timestamp=time.time()
                )
                self.queue.add_event(file_event)
        
        def on_created(self, event):
            if not event.is_directory and self._is_code_file(event.src_path):
                file_event = FileEvent(
                    file_path=event.src_path,
                    event_type=FileEventType.CREATED,
                    timestamp=time.time()
                )
                self.queue.add_event(file_event)
        
        def on_deleted(self, event):
            if not event.is_directory and self._is_code_file(event.src_path):
                file_event = FileEvent(
                    file_path=event.src_path,
                    event_type=FileEventType.DELETED,
                    timestamp=time.time()
                )
                self.queue.add_event(file_event)
else:
    # Dummy class for when watchdog is not available
    class CodeFileEventHandler:
        pass


class FileMonitor:
    """
    Cross-platform file monitor for code files.
    Supports both watchdog-based and polling-based monitoring.
    """
    
    def __init__(self, project_path: str, debounce_window_ms: float = 1000.0):
        self.project_path = os.path.abspath(project_path)
        self.debounce_queue = DebounceMergeQueue(debounce_window_ms)
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[CodeFileEventHandler] = None
        self.is_running = False
        self.poll_thread: Optional[threading.Thread] = None
        self._stop_polling = threading.Event()
    
    def set_event_callback(self, callback: Callable[[FileEvent], None]):
        """Set callback for file events."""
        self.debounce_queue.set_callback(callback)
    
    def start(self):
        """Start file monitoring."""
        if self.is_running:
            return
        
        self.is_running = True
        
        if WATCHDOG_AVAILABLE:
            self._start_watchdog()
        else:
            self._start_polling()
    
    def _start_watchdog(self):
        """Start watchdog-based monitoring."""
        self.event_handler = CodeFileEventHandler(self.debounce_queue)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.project_path, recursive=True)
        self.observer.start()
        print(f"Started watchdog monitoring: {self.project_path}")
    
    def _start_polling(self):
        """Start polling-based monitoring (fallback)."""
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()
        print(f"Started polling monitoring: {self.project_path}")
    
    def _poll_loop(self):
        """Polling loop for file changes."""
        file_states: Dict[str, float] = {}
        poll_interval = 1.0  # seconds
        skip_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.venv',
                     'dist', 'build', '.idea', '.vscode'}

        # Initialize file states
        for root, dirs, files in os.walk(self.project_path):
            # Skip hidden and non-code directories
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]

            for filename in files:
                filepath = os.path.join(root, filename)
                if self._is_code_file(filepath):
                    try:
                        mtime = os.path.getmtime(filepath)
                        file_states[filepath] = mtime
                    except OSError:
                        pass
        
        while not self._stop_polling.is_set():
            time.sleep(poll_interval)
            
            current_files: Set[str] = set()
            
            for root, dirs, files in os.walk(self.project_path):
                dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
                
                for filename in files:
                    filepath = os.path.join(root, filename)
                    if not self._is_code_file(filepath):
                        continue
                    
                    current_files.add(filepath)
                    
                    try:
                        mtime = os.path.getmtime(filepath)
                        
                        if filepath not in file_states:
                            # New file
                            event = FileEvent(
                                file_path=filepath,
                                event_type=FileEventType.CREATED,
                                timestamp=time.time()
                            )
                            self.debounce_queue.add_event(event)
                        elif mtime > file_states[filepath]:
                            # Modified file
                            event = FileEvent(
                                file_path=filepath,
                                event_type=FileEventType.MODIFIED,
                                timestamp=time.time()
                            )
                            self.debounce_queue.add_event(event)
                        
                        file_states[filepath] = mtime
                    except OSError:
                        pass
            
            # Check for deleted files
            for filepath in list(file_states.keys()):
                if filepath not in current_files:
                    event = FileEvent(
                        file_path=filepath,
                        event_type=FileEventType.DELETED,
                        timestamp=time.time()
                    )
                    self.debounce_queue.add_event(event)
                    del file_states[filepath]
    
    def _is_code_file(self, file_path: str) -> bool:
        """Check if file is a code file."""
        parts = file_path.split(os.sep)
        for part in parts:
            if part.startswith('.') and part not in ('.', '..'):
                return False
            if part in ('node_modules', '__pycache__', 'venv', '.git', 'dist', 'build'):
                return False
        
        ext = os.path.splitext(file_path)[1].lower()
        return ext in {'.py', '.java', '.js', '.jsx', '.ts', '.tsx', '.go', '.rs',
                       '.c', '.h', '.cpp', '.hpp', '.cs', '.php', '.rb', '.swift',
                       '.kt', '.scala', '.dart', '.lua'}
    
    def stop(self):
        """Stop file monitoring."""
        self.is_running = False
        self._stop_polling.set()
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        if self.poll_thread:
            self.poll_thread.join(timeout=2.0)
        
        self.debounce_queue.shutdown()
        print("File monitoring stopped")
    
    def get_event(self, timeout: Optional[float] = None) -> Optional[FileEvent]:
        """Get a file event from the queue."""
        return self.debounce_queue.get_event(timeout)


if __name__ == '__main__':
    import sys
    
    def event_callback(event: FileEvent):
        print(f"[{event.event_type.value}] {event.file_path}")
    
    # Test with current directory
    test_path = sys.argv[1] if len(sys.argv) > 1 else '.'
    
    monitor = FileMonitor(test_path, debounce_window_ms=500)
    monitor.set_event_callback(event_callback)
    monitor.start()
    
    print(f"Monitoring {test_path}... Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()
