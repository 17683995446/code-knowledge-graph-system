"""
System Tests Module
End-to-end system tests simulating real-world usage scenarios.
"""

import os
import sys
import unittest
import tempfile
import shutil
import time
import subprocess
import signal
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main_service import CodeKnowledgeGraphService


class TestSystemStartup(unittest.TestCase):
    """Tests for system startup and initialization."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_service_initialization(self):
        """Test service can be initialized."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            # Verify database was created
            self.assertTrue(os.path.exists(self.db_path))
            
            # Verify components are initialized
            self.assertIsNotNone(service.db_manager)
            self.assertIsNotNone(service.update_engine)
        finally:
            service.stop()
    
    def test_service_statistics(self):
        """Test service statistics functionality."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            # Create a test file
            with open(os.path.join(self.project_dir, "test.py"), 'w') as f:
                f.write("class Test: pass")
            
            # Perform sync
            service.perform_full_sync()
            
            # Get statistics
            stats = service.get_statistics()
            
            self.assertIn('database', stats)
            self.assertIn('files_by_language', stats)
            self.assertIn('total_updates', stats)
            
            self.assertEqual(stats['database']['files'], 1)
        finally:
            service.stop()


class TestMultiLanguageSupport(unittest.TestCase):
    """Tests for multi-language support."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
        
        # Create multi-language project
        self.files = {
            "app.py": "class App: pass",
            "utils.py": "def helper(): pass",
            "Main.java": "public class Main { }",
            "script.js": "function main() { }",
            "helper.go": "package main\nfunc Help() { }"
        }
        
        for filename, content in self.files.items():
            filepath = os.path.join(self.project_dir, filename)
            with open(filepath, 'w') as f:
                f.write(content)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_language_detection(self):
        """Test language detection for different file types."""
        from parser_interface import get_language_by_extension
        
        self.assertEqual(get_language_by_extension("test.py"), "python")
        self.assertEqual(get_language_by_extension("test.java"), "java")
        self.assertEqual(get_language_by_extension("test.js"), "javascript")
        self.assertEqual(get_language_by_extension("test.go"), "go")
    
    def test_multi_language_sync(self):
        """Test syncing files of multiple languages."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            result = service.perform_full_sync()
            
            # 2 Python files are processed successfully; 3 non-Python files fail
            # (no registered parsers for Java, Go, JavaScript)
            self.assertEqual(result['files_updated'], 2)  # Only Python files
            self.assertEqual(len(result['errors']), 3)    # Java, Go, JS have no parsers
            
            # Verify database state - only Python files stored
            stats = service.get_statistics()
            self.assertEqual(stats['database']['files'], 2)  # Only Python files
            
            # Check language distribution
            file_stats = stats['files_by_language']
            self.assertIn('python', file_stats)
        finally:
            service.stop()


class TestPerformanceRequirements(unittest.TestCase):
    """Tests for performance requirements."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_single_file_update_time(self):
        """Test that single file updates complete within 2 seconds."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            # Create a file
            test_file = os.path.join(self.project_dir, "perf_test.py")
            with open(test_file, 'w') as f:
                f.write("class Test:\n    def method(self):\n        pass\n")
                for i in range(99):
                    f.write(f"    def method{i}(self):\n        pass\n")
            
            # Measure update time
            from file_monitor_module import FileEvent, FileEventType
            
            start_time = time.time()
            event = FileEvent(test_file, FileEventType.CREATED, time.time())
            result = service.update_engine.process_file_event(event)
            elapsed = time.time() - start_time
            
            self.assertTrue(result.success)
            self.assertLess(elapsed, 2.0, f"Update took {elapsed:.2f}s, expected < 2s")
            self.assertLess(result.processing_time_ms, 2000)
        finally:
            service.stop()
    
    def test_large_file_handling(self):
        """Test handling of larger files."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            # Create a larger file (1000 lines)
            test_file = os.path.join(self.project_dir, "large.py")
            with open(test_file, 'w') as f:
                for i in range(100):
                    f.write(f"class Class{i}:\n    def method(self):\n        pass\n")
            
            from file_monitor_module import FileEvent, FileEventType
            event = FileEvent(test_file, FileEventType.CREATED, time.time())
            result = service.update_engine.process_file_event(event)
            
            self.assertTrue(result.success)
            self.assertEqual(result.types_count, 100)
        finally:
            service.stop()


class TestConcurrencyAndReliability(unittest.TestCase):
    """Tests for concurrency and reliability."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_rapid_file_changes(self):
        """Test handling rapid file changes."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            test_file = os.path.join(self.project_dir, "rapid.py")
            
            from file_monitor_module import FileEvent, FileEventType
            
            # Simulate rapid changes
            for i in range(5):
                with open(test_file, 'w') as f:
                    f.write(f"class Test{i}: pass")
                
                event = FileEvent(test_file, FileEventType.MODIFIED, time.time())
                result = service.update_engine.process_file_event(event)
                self.assertTrue(result.success)
            
            # Verify final state
            stats = service.get_statistics()
            self.assertEqual(stats['database']['files'], 1)
            self.assertEqual(stats['database']['types'], 1)
        finally:
            service.stop()
    
    def test_database_integrity(self):
        """Test database integrity after operations."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            # Create multiple files
            for i in range(5):
                filepath = os.path.join(self.project_dir, f"file{i}.py")
                with open(filepath, 'w') as f:
                    f.write(f"class Class{i}:\n    def method(self): pass")
            
            service.perform_full_sync()
            
            # Delete some files
            for i in range(3):
                os.remove(os.path.join(self.project_dir, f"file{i}.py"))
            
            service.perform_full_sync()
            
            # Verify integrity
            stats = service.get_statistics()
            self.assertEqual(stats['database']['files'], 2)
            self.assertEqual(stats['database']['types'], 2)
        finally:
            service.stop()


class TestErrorHandling(unittest.TestCase):
    """Tests for error handling."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_invalid_file_handling(self):
        """Test handling of invalid files."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            from file_monitor_module import FileEvent, FileEventType
            
            # Try to process non-existent file
            event = FileEvent(
                os.path.join(self.project_dir, "nonexistent.py"),
                FileEventType.MODIFIED,
                time.time()
            )
            result = service.update_engine.process_file_event(event)
            
            # Should fail gracefully
            self.assertFalse(result.success)
            self.assertIsNotNone(result.error_message)
        finally:
            service.stop()
    
    def test_malformed_code_handling(self):
        """Test handling of malformed code."""
        service = CodeKnowledgeGraphService(
            project_path=self.project_dir,
            database_path=self.db_path
        )
        
        try:
            service.initialize()
            
            # Create file with syntax errors
            test_file = os.path.join(self.project_dir, "broken.py")
            with open(test_file, 'w') as f:
                f.write("class Test:\n    def method(\n        # Missing closing parenthesis")
            
            from file_monitor_module import FileEvent, FileEventType
            event = FileEvent(test_file, FileEventType.CREATED, time.time())
            result = service.update_engine.process_file_event(event)
            
            # Parser should handle gracefully (may succeed with partial results or fail gracefully)
            self.assertIsNotNone(result)
        finally:
            service.stop()


class TestWebInterface(unittest.TestCase):
    """Tests for web interface functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
        
        # Create test file
        with open(os.path.join(self.project_dir, "app.py"), 'w') as f:
            f.write("class App:\n    def run(self): pass")
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_web_server_api(self):
        """Test web server API endpoints."""
        from web_server import KnowledgeGraphServer
        
        server = KnowledgeGraphServer(
            self.project_dir,
            self.db_path,
            api_key=None,
            host='127.0.0.1',
            port=5556
        )
        
        try:
            server.db_manager.initialize_schema()
            server.update_engine.perform_full_sync(self.project_dir)
            
            with server.app.test_client() as client:
                # Test all major endpoints
                endpoints = [
                    '/api/status',
                    '/api/statistics',
                    '/api/files',
                    '/api/types',
                    '/api/functions',
                    '/api/graph'
                ]
                
                for endpoint in endpoints:
                    response = client.get(endpoint)
                    self.assertEqual(response.status_code, 200, f"Endpoint {endpoint} failed")
        finally:
            server.stop_monitoring()
            server.db_manager.close()


def run_system_tests():
    """Run all system tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestSystemStartup))
    suite.addTests(loader.loadTestsFromTestCase(TestMultiLanguageSupport))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceRequirements))
    suite.addTests(loader.loadTestsFromTestCase(TestConcurrencyAndReliability))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    suite.addTests(loader.loadTestsFromTestCase(TestWebInterface))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_system_tests()
    sys.exit(0 if success else 1)
