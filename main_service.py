"""
Main Service Module
Entry point for the code knowledge graph system.
Coordinates all components and provides CLI interface.
"""

import os
import sys
import argparse
import signal
import time
import threading
from typing import Optional

from database_schema import DatabaseManager, create_database
from incremental_update_engine import IncrementalUpdateEngine
from file_monitor_module import FileMonitor, FileEvent, FileEventType
from web_server import KnowledgeGraphServer
from architecture_diagram import save_all_diagrams

# Import parsers to register them
import python_parser


class CodeKnowledgeGraphService:
    """
    Main service for the code knowledge graph system.
    Manages all components and provides lifecycle management.
    """
    
    def __init__(self, project_path: str, database_path: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.project_path = os.path.abspath(project_path)
        self.database_path = database_path or os.path.join(
            os.path.dirname(__file__), 'data', 'knowledge_graph.db'
        )
        self.api_key = api_key
        
        # Components
        self.db_manager: Optional[DatabaseManager] = None
        self.update_engine: Optional[IncrementalUpdateEngine] = None
        self.file_monitor: Optional[FileMonitor] = None
        self.web_server: Optional[KnowledgeGraphServer] = None
        
        # State
        self.is_running = False
        self.update_count = 0
        self._count_lock = threading.Lock()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        print(f"\nReceived signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def initialize(self):
        """Initialize all components."""
        print("Initializing Code Knowledge Graph System...")
        print(f"Project path: {self.project_path}")
        print(f"Database path: {self.database_path}")
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'static', 'diagrams'), exist_ok=True)
        
        # Initialize database
        create_database(self.database_path)
        self.db_manager = DatabaseManager(self.database_path)
        self.db_manager.connect()
        
        # Initialize update engine
        self.update_engine = IncrementalUpdateEngine(self.db_manager)
        
        # Generate diagrams
        print("Generating system diagrams...")
        diagrams_dir = os.path.join(os.path.dirname(__file__), 'static', 'diagrams')
        saved_diagrams = save_all_diagrams(diagrams_dir)
        print(f"Generated {len(saved_diagrams)} diagrams")
        
        print("Initialization complete.")
    
    def perform_full_sync(self):
        """Perform full project synchronization."""
        print("\nPerforming full project synchronization...")
        start_time = time.time()
        
        result = self.update_engine.perform_full_sync(self.project_path)
        
        elapsed = time.time() - start_time
        print(f"\nSync completed in {elapsed:.2f} seconds:")
        print(f"  Files updated: {result['files_updated']}")
        print(f"  Files deleted: {result['files_deleted']}")
        print(f"  Files unchanged: {result['files_unchanged']}")
        
        if result['errors']:
            print(f"  Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:
                print(f"    - {error}")
        
        with self._count_lock:
            self.update_count += result['files_updated']
        return result
    
    def start_monitoring(self):
        """Start file monitoring."""
        if self.file_monitor:
            return
        
        print("\nStarting file monitor...")
        self.file_monitor = FileMonitor(self.project_path)
        
        def on_file_event(event: FileEvent):
            print(f"[{event.event_type.value}] {event.file_path}")
            result = self.update_engine.process_file_event(event)
            if result.success:
                with self._count_lock:
                    self.update_count += 1
                print(f"  -> Processed in {result.processing_time_ms:.1f}ms")
            else:
                print(f"  -> Error: {result.error_message}")
        
        self.file_monitor.set_event_callback(on_file_event)
        self.file_monitor.start()
        print("File monitor started.")
    
    def stop_monitoring(self):
        """Stop file monitoring."""
        if self.file_monitor:
            self.file_monitor.stop()
            self.file_monitor = None
            print("File monitor stopped.")
    
    def start_web_server(self, host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
        """Start the web server."""
        print(f"\nStarting web server at http://{host}:{port}")
        
        self.web_server = KnowledgeGraphServer(
            self.project_path, 
            self.database_path,
            self.api_key,
            host, 
            port,
            db_manager=self.db_manager,
            update_engine=self.update_engine
        )
        
        # Pass existing file_monitor to web_server to avoid double monitoring
        if self.file_monitor:
            self.web_server.file_monitor = self.file_monitor
        
        # Start monitoring if not already running
        if not self.file_monitor:
            self.start_monitoring()
        
        self.web_server.run(debug=debug)
    
    def start(self, sync_first: bool = True, monitor: bool = True, 
              web: bool = True, host: str = '0.0.0.0', port: int = 5000):
        """Start the complete service."""
        self.initialize()
        
        if sync_first:
            self.perform_full_sync()
        
        if monitor:
            self.start_monitoring()
        
        if web:
            self.start_web_server(host, port)
        else:
            self.is_running = True
            print("\nService running. Press Ctrl+C to stop.")
            try:
                while self.is_running:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                self.stop()
    
    def stop(self):
        """Stop all components."""
        print("\nStopping service...")
        self.is_running = False
        
        self.stop_monitoring()
        
        if self.db_manager:
            self.db_manager.close()
            self.db_manager = None
        
        print("Service stopped.")
    
    def get_knowledge_graph(self):
        """Get the knowledge graph data.

        Returns the knowledge graph from the web server if available,
        otherwise returns an empty result to avoid NoneType errors.
        """
        if self.web_server is not None:
            return self.web_server._get_knowledge_graph()
        return {'nodes': [], 'edges': []}

    def get_statistics(self):
        """Get current system statistics."""
        if not self.db_manager:
            return {}
        
        db_stats = self.db_manager.get_statistics()
        file_stats = self.db_manager.get_file_statistics()
        
        # Map relationships back to references for API compatibility
        api_stats = {
            'files': db_stats.get('files', 0),
            'types': db_stats.get('types', 0),
            'functions': db_stats.get('functions', 0),
            'calls': db_stats.get('calls', 0),
            'references': db_stats.get('relationships', 0)
        }
        
        return {
            'database': api_stats,
            'files_by_language': file_stats,
            'total_updates': self.update_count
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Code Knowledge Graph System - Universal code analysis platform'
    )
    
    parser.add_argument('project_path', nargs='?', default='.',
                       help='Path to the project to analyze (default: current directory)')
    parser.add_argument('--database', '-d', default=None,
                       help='Path to the SQLite database file')
    parser.add_argument('--sync', '-s', action='store_true',
                       help='Perform full sync and exit')
    parser.add_argument('--no-sync', action='store_true',
                       help='Skip initial full sync')
    parser.add_argument('--no-monitor', action='store_true',
                       help='Disable file monitoring')
    parser.add_argument('--no-web', action='store_true',
                       help='Disable web server')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Web server host (default: 0.0.0.0)')
    parser.add_argument('--port', '-p', type=int, default=5000,
                       help='Web server port (default: 5000)')
    parser.add_argument('--api-key', '-k', default=None,
                       help='Silicon Flow API key for LLM analysis')
    
    args = parser.parse_args()
    
    # Get API key from environment if not provided
    api_key = args.api_key or os.environ.get('SILICON_FLOW_API_KEY')
    
    # Create and run service
    service = CodeKnowledgeGraphService(
        project_path=args.project_path,
        database_path=args.database,
        api_key=api_key
    )
    
    if args.sync:
        # Sync only mode
        service.initialize()
        service.perform_full_sync()
        service.stop()
    else:
        # Full service mode
        service.start(
            sync_first=not args.no_sync,
            monitor=not args.no_monitor,
            web=not args.no_web,
            host=args.host,
            port=args.port
        )


if __name__ == '__main__':
    main()
