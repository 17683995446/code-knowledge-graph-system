"""
Integration Tests Module
Tests component interactions and end-to-end workflows.
"""

import os
import sys
import unittest
import tempfile
import shutil
import time
import threading
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_schema import DatabaseManager, create_database
from incremental_update_engine import IncrementalUpdateEngine
from file_monitor_module import FileMonitor, FileEvent, FileEventType
from python_parser import PythonParser
from parser_interface import register_parser
from web_server import KnowledgeGraphServer


class TestParserToDatabaseIntegration(unittest.TestCase):
    """Integration tests for parser and database."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_database(self.db_path)
        self.db = DatabaseManager(self.db_path)
        self.db.connect()
        self.engine = IncrementalUpdateEngine(self.db)
        
        # Create test project
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
    
    def tearDown(self):
        """Clean up."""
        self.db.close()
        shutil.rmtree(self.temp_dir)
    
    def test_parse_and_store_file(self):
        """Test parsing a file and storing in database."""
        # Create test Python file
        test_file = os.path.join(self.project_dir, "test_module.py")
        with open(test_file, 'w') as f:
            f.write('''
class DataProcessor:
    def process(self, data):
        return self.transform(data)
    
    def transform(self, data):
        return data.upper()

def main():
    processor = DataProcessor()
    result = processor.process("hello")
    print(result)
''')
        
        # Process file
        event = FileEvent(
            file_path=test_file,
            event_type=FileEventType.CREATED,
            timestamp=time.time()
        )
        result = self.engine.process_file_event(event)
        
        # Verify success
        self.assertTrue(result.success)
        self.assertEqual(result.types_count, 1)
        self.assertEqual(result.functions_count, 3)  # process, transform, main
        
        # Verify database state
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 1)
        self.assertEqual(stats['types'], 1)
        self.assertEqual(stats['functions'], 3)
    
    def test_update_existing_file(self):
        """Test updating an existing file."""
        test_file = os.path.join(self.project_dir, "module.py")
        
        # Create initial file
        with open(test_file, 'w') as f:
            f.write('class A: pass')
        
        event = FileEvent(test_file, FileEventType.CREATED, time.time())
        self.engine.process_file_event(event)
        
        # Verify initial state
        stats = self.db.get_statistics()
        self.assertEqual(stats['types'], 1)
        
        # Update file
        with open(test_file, 'w') as f:
            f.write('class A: pass\nclass B: pass')
        
        event = FileEvent(test_file, FileEventType.MODIFIED, time.time())
        result = self.engine.process_file_event(event)
        
        # Verify updated state
        self.assertTrue(result.success)
        stats = self.db.get_statistics()
        self.assertEqual(stats['types'], 2)
        self.assertEqual(stats['files'], 1)  # Still one file
    
    def test_delete_file(self):
        """Test deleting a file."""
        test_file = os.path.join(self.project_dir, "temp.py")
        
        # Create and process file
        with open(test_file, 'w') as f:
            f.write('class Temp: pass')
        
        event = FileEvent(test_file, FileEventType.CREATED, time.time())
        self.engine.process_file_event(event)
        
        # Verify file exists
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 1)
        
        # Delete file
        event = FileEvent(test_file, FileEventType.DELETED, time.time())
        result = self.engine.process_file_event(event)
        
        # Verify deletion
        self.assertTrue(result.success)
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 0)
        self.assertEqual(stats['types'], 0)


class TestFileMonitorIntegration(unittest.TestCase):
    """Integration tests for file monitor."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_database(self.db_path)
        self.db = DatabaseManager(self.db_path)
        self.db.connect()
        self.engine = IncrementalUpdateEngine(self.db)
        
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
        
        # Create file monitor
        self.monitor = FileMonitor(self.project_dir, debounce_window_ms=200)
        
        # Track received events
        self.received_events = []
        def on_event(event):
            self.received_events.append(event)
            self.engine.process_file_event(event)
        
        self.monitor.set_event_callback(on_event)
    
    def tearDown(self):
        """Clean up."""
        self.monitor.stop()
        self.db.close()
        shutil.rmtree(self.temp_dir)
    
    def test_monitor_detects_new_file(self):
        """Test that monitor detects new files."""
        self.monitor.start()
        
        # Wait for initial polling scan to complete (poll_interval=1.0s)
        time.sleep(1.5)
        
        # Create a new file AFTER init scan
        test_file = os.path.join(self.project_dir, "new_file.py")
        with open(test_file, 'w') as f:
            f.write("# New file")
        
        # Wait for next poll cycle + debounce
        time.sleep(2.0)
        
        # Verify event was received
        self.assertTrue(len(self.received_events) > 0)
        self.assertEqual(self.received_events[0].event_type, FileEventType.CREATED)
    
    def test_monitor_detects_modifications(self):
        """Test that monitor detects file modifications."""
        # Create initial file
        test_file = os.path.join(self.project_dir, "watch.py")
        with open(test_file, 'w') as f:
            f.write("# Initial")
        
        self.monitor.start()
        time.sleep(1.5)  # Wait for initial polling scan to complete
        
        # Clear initial events
        self.received_events.clear()
        
        # Modify file
        with open(test_file, 'w') as f:
            f.write("# Modified")
        
        # Wait for debounce + polling interval (poll_interval=1.0s)
        time.sleep(2.0)
        
        # Verify modification was detected
        mod_events = [e for e in self.received_events if e.event_type == FileEventType.MODIFIED]
        self.assertTrue(len(mod_events) > 0)


class TestFullSyncIntegration(unittest.TestCase):
    """Integration tests for full sync functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_database(self.db_path)
        self.db = DatabaseManager(self.db_path)
        self.db.connect()
        self.engine = IncrementalUpdateEngine(self.db)
        
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
    
    def tearDown(self):
        """Clean up."""
        self.db.close()
        shutil.rmtree(self.temp_dir)
    
    def test_full_sync_multiple_files(self):
        """Test full sync with multiple files."""
        # Create multiple Python files
        files_content = {
            "module_a.py": "class A: pass",
            "module_b.py": "class B: pass",
            "utils.py": "def helper(): pass"
        }
        
        for filename, content in files_content.items():
            filepath = os.path.join(self.project_dir, filename)
            with open(filepath, 'w') as f:
                f.write(content)
        
        # Perform full sync
        result = self.engine.perform_full_sync(self.project_dir)
        
        # Verify results
        self.assertEqual(result['files_updated'], 3)
        self.assertEqual(result['files_deleted'], 0)
        
        # Verify database state
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 3)
        self.assertEqual(stats['types'], 2)  # A and B
        self.assertEqual(stats['functions'], 1)  # helper
    
    def test_full_sync_detects_deletions(self):
        """Test that full sync detects deleted files."""
        # Create and sync initial files
        test_file = os.path.join(self.project_dir, "temp.py")
        with open(test_file, 'w') as f:
            f.write("class Temp: pass")
        
        self.engine.perform_full_sync(self.project_dir)
        
        # Verify initial state
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 1)
        
        # Delete file
        os.remove(test_file)
        
        # Sync again
        result = self.engine.perform_full_sync(self.project_dir)
        
        # Verify deletion detected
        self.assertEqual(result['files_deleted'], 1)
        
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 0)


class TestWebServerIntegration(unittest.TestCase):
    """Integration tests for web server."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_database(self.db_path)
        
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
        
        # Create test file
        with open(os.path.join(self.project_dir, "app.py"), 'w') as f:
            f.write("class App: pass")
        
        # Create server (don't run it)
        self.server = KnowledgeGraphServer(
            self.project_dir,
            self.db_path,
            api_key=None,
            host='127.0.0.1',
            port=5555
        )
        
        # Initialize
        self.server.db_manager.initialize_schema()
    
    def tearDown(self):
        """Clean up."""
        self.server.stop_monitoring()
        self.server.db_manager.close()
        shutil.rmtree(self.temp_dir)
    
    def test_server_initialization(self):
        """Test server initialization."""
        self.assertIsNotNone(self.server.db_manager)
        self.assertIsNotNone(self.server.update_engine)
    
    def test_api_status(self):
        """Test status API endpoint."""
        with self.server.app.test_client() as client:
            response = client.get('/api/status')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('status', data)
            self.assertIn('project_path', data)
    
    def test_api_statistics(self):
        """Test statistics API endpoint."""
        # First sync some data
        self.server.update_engine.perform_full_sync(self.project_dir)
        
        with self.server.app.test_client() as client:
            response = client.get('/api/statistics')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('total_files', data)
            self.assertIn('total_types', data)
            self.assertIn('languages', data)
    
    def test_api_files(self):
        """Test files API endpoint."""
        # Sync data first
        self.server.update_engine.perform_full_sync(self.project_dir)
        
        with self.server.app.test_client() as client:
            response = client.get('/api/files')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('files', data)
            self.assertIn('count', data)
            self.assertEqual(data['count'], 1)
    
    def test_api_sync(self):
        """Test sync API endpoint."""
        with self.server.app.test_client() as client:
            response = client.post('/api/sync')
            self.assertEqual(response.status_code, 200)
            
            data = response.get_json()
            self.assertIn('files_updated', data)
            self.assertIn('files_deleted', data)


class TestEndToEndWorkflow(unittest.TestCase):
    """End-to-end workflow tests."""
    
    def setUp(self):
        """Set up complete test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
        
        # Initialize database
        create_database(self.db_path)
        self.db = DatabaseManager(self.db_path)
        self.db.connect()
        self.engine = IncrementalUpdateEngine(self.db)
    
    def tearDown(self):
        """Clean up."""
        self.db.close()
        shutil.rmtree(self.temp_dir)
    
    def test_complete_workflow(self):
        """Test complete workflow: create, modify, delete."""
        # Step 1: Create initial project structure
        files = {
            "main.py": '''
from utils import helper

class MainApp:
    def run(self):
        return helper()
''',
            "utils.py": '''
def helper():
    return "helped"

def unused():
    pass
'''
        }
        
        for filename, content in files.items():
            filepath = os.path.join(self.project_dir, filename)
            with open(filepath, 'w') as f:
                f.write(content)
        
        # Step 2: Full sync
        result = self.engine.perform_full_sync(self.project_dir)
        self.assertEqual(result['files_updated'], 2)
        
        # Step 3: Verify database state
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 2)
        self.assertEqual(stats['types'], 1)  # MainApp
        self.assertEqual(stats['functions'], 3)  # run, helper, unused
        
        # Step 4: Modify a file
        with open(os.path.join(self.project_dir, "utils.py"), 'w') as f:
            f.write('''
def helper():
    return "improved helper"
''')
        
        event = FileEvent(
            os.path.join(self.project_dir, "utils.py"),
            FileEventType.MODIFIED,
            time.time()
        )
        result = self.engine.process_file_event(event)
        self.assertTrue(result.success)
        
        # Step 5: Verify updated state
        stats = self.db.get_statistics()
        self.assertEqual(stats['functions'], 2)  # run, helper (unused removed)
        
        # Step 6: Delete a file
        event = FileEvent(
            os.path.join(self.project_dir, "utils.py"),
            FileEventType.DELETED,
            time.time()
        )
        result = self.engine.process_file_event(event)
        self.assertTrue(result.success)
        
        # Step 7: Verify final state
        stats = self.db.get_statistics()
        self.assertEqual(stats['files'], 1)
        self.assertEqual(stats['functions'], 1)  # Only run remains


def run_integration_tests():
    """Run all integration tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestParserToDatabaseIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestFileMonitorIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestFullSyncIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestWebServerIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndWorkflow))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_integration_tests()
    sys.exit(0 if success else 1)
