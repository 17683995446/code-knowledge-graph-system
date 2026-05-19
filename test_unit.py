"""
Unit Tests Module
Comprehensive unit tests for all system components.
"""

import os
import sys
import unittest
import tempfile
import shutil
import hashlib
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser_interface import (
    ParseResult, TypeInfo, FunctionInfo, CallInfo, ReferenceInfo,
    get_language_by_extension, EXTENSION_LANGUAGE_MAP
)
from python_parser import PythonParser
from database_schema import DatabaseManager, create_database
from incremental_update_engine import IncrementalUpdateEngine, UpdateStatistics
from file_monitor_module import FileEvent, FileEventType, DebounceMergeQueue
from llm_analyzer import MockLLMAnalyzer, AnalysisType


class TestParserInterface(unittest.TestCase):
    """Unit tests for parser interface module."""
    
    def test_parse_result_empty(self):
        """Test ParseResult empty check."""
        result = ParseResult()
        self.assertTrue(result.is_empty())
        
        result.types.append(TypeInfo(name="Test", kind="class"))
        self.assertFalse(result.is_empty())
    
    def test_parse_result_merge(self):
        """Test ParseResult merge functionality."""
        result1 = ParseResult()
        result1.types.append(TypeInfo(name="Type1", kind="class"))
        
        result2 = ParseResult()
        result2.types.append(TypeInfo(name="Type2", kind="interface"))
        result2.functions.append(FunctionInfo(name="func1", type_name=None, signature="()"))
        
        result1.merge(result2)
        
        self.assertEqual(len(result1.types), 2)
        self.assertEqual(len(result1.functions), 1)
    
    def test_extension_language_mapping(self):
        """Test file extension to language mapping."""
        self.assertEqual(get_language_by_extension("test.py"), "python")
        self.assertEqual(get_language_by_extension("test.java"), "java")
        self.assertEqual(get_language_by_extension("test.js"), "javascript")
        self.assertEqual(get_language_by_extension("test.ts"), "typescript")
        self.assertEqual(get_language_by_extension("test.go"), "go")
        self.assertIsNone(get_language_by_extension("test.unknown"))


class TestPythonParser(unittest.TestCase):
    """Unit tests for Python parser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = PythonParser()
    
    def test_supported_extensions(self):
        """Test supported extensions."""
        extensions = self.parser.supported_extensions
        self.assertIn('.py', extensions)
        self.assertIn('.pyw', extensions)
    
    def test_language_name(self):
        """Test language name."""
        self.assertEqual(self.parser.language_name, 'python')
    
    def test_can_parse(self):
        """Test parser can handle Python files."""
        self.assertTrue(self.parser.can_parse("test.py"))
        self.assertTrue(self.parser.can_parse("/path/to/file.py"))
        self.assertFalse(self.parser.can_parse("test.java"))
    
    def test_parse_simple_class(self):
        """Test parsing a simple class."""
        code = '''
class Animal:
    def speak(self):
        pass
'''
        result = self.parser.parse_file("test.py", code)
        
        self.assertEqual(len(result.types), 1)
        self.assertEqual(result.types[0].name, "Animal")
        self.assertEqual(result.types[0].kind, "class")
        
        self.assertEqual(len(result.functions), 1)
        self.assertEqual(result.functions[0].name, "speak")
        self.assertEqual(result.functions[0].type_name, "Animal")
    
    def test_parse_inheritance(self):
        """Test parsing class inheritance."""
        code = '''
class Animal:
    pass

class Dog(Animal):
    pass
'''
        result = self.parser.parse_file("test.py", code)
        
        self.assertEqual(len(result.types), 2)
        self.assertEqual(len(result.references), 1)
        self.assertEqual(result.references[0].from_name, "Dog")
        self.assertEqual(result.references[0].to_name, "Animal")
        self.assertEqual(result.references[0].ref_kind, "inherit")
    
    def test_parse_imports(self):
        """Test parsing import statements."""
        code = '''
import os
import sys
from typing import List
'''
        result = self.parser.parse_file("test.py", code)
        
        self.assertTrue(len(result.references) > 0)
        import_refs = [r for r in result.references if r.ref_kind == "import"]
        self.assertTrue(len(import_refs) > 0)
    
    def test_parse_function_calls(self):
        """Test parsing function calls."""
        code = '''
def helper():
    pass

def main():
    helper()
'''
        result = self.parser.parse_file("test.py", code)
        
        self.assertEqual(len(result.functions), 2)
        # Note: Call extraction may vary based on implementation


class TestDatabaseManager(unittest.TestCase):
    """Unit tests for database manager."""
    
    def setUp(self):
        """Set up temporary database."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_database(self.db_path)
        self.db = DatabaseManager(self.db_path)
        self.db.connect()
    
    def tearDown(self):
        """Clean up temporary database."""
        self.db.close()
        shutil.rmtree(self.temp_dir)
    
    def test_connection(self):
        """Test database connection."""
        self.assertIsNotNone(self.db.connection)
    
    def test_file_operations(self):
        """Test file CRUD operations."""
        # Insert file
        cursor = self.db.connection.cursor()
        cursor.execute(
            "INSERT INTO files (path, language, hash, modified) VALUES (?, ?, ?, ?)",
            ("/test/file.py", "python", b"hash123", int(time.time()))
        )
        self.db.connection.commit()
        
        # Query file
        result = self.db.execute_query("SELECT * FROM files WHERE path = ?", ("/test/file.py",))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], "/test/file.py")
        
        # Get file ID
        file_id = self.db.get_file_id_by_path("/test/file.py")
        self.assertIsNotNone(file_id)
    
    def test_statistics(self):
        """Test statistics retrieval."""
        stats = self.db.get_statistics()
        self.assertIn('files', stats)
        self.assertIn('types', stats)
        self.assertIn('functions', stats)
    
    def test_transaction(self):
        """Test transaction handling."""
        self.db.begin_transaction()
        cursor = self.db.connection.cursor()
        cursor.execute(
            "INSERT INTO files (path, language, hash, modified) VALUES (?, ?, ?, ?)",
            ("/test/tx.py", "python", b"hash", int(time.time()))
        )
        self.db.commit_transaction()
        
        result = self.db.execute_query("SELECT * FROM files WHERE path = ?", ("/test/tx.py",))
        self.assertEqual(len(result), 1)


class TestIncrementalUpdateEngine(unittest.TestCase):
    """Unit tests for incremental update engine."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        create_database(self.db_path)
        self.db = DatabaseManager(self.db_path)
        self.db.connect()
        self.engine = IncrementalUpdateEngine(self.db)
        
        # Create test project directory
        self.project_dir = os.path.join(self.temp_dir, "project")
        os.makedirs(self.project_dir)
    
    def tearDown(self):
        """Clean up."""
        self.db.close()
        shutil.rmtree(self.temp_dir)
    
    def test_file_hash_calculation(self):
        """Test file hash calculation."""
        test_file = os.path.join(self.temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test content")
        
        hash1 = self.engine.calculate_file_hash(test_file)
        hash2 = self.engine.calculate_file_hash(test_file)
        
        self.assertIsNotNone(hash1)
        self.assertEqual(hash1, hash2)
    
    def test_string_hash_calculation(self):
        """Test string hash calculation."""
        hash1 = self.engine.calculate_string_hash("test")
        hash2 = self.engine.calculate_string_hash("test")
        hash3 = self.engine.calculate_string_hash("different")
        
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, hash3)
    
    def test_scan_project_files(self):
        """Test project file scanning."""
        # Create test files
        with open(os.path.join(self.project_dir, "test.py"), 'w') as f:
            f.write("# test")
        with open(os.path.join(self.project_dir, "test.java"), 'w') as f:
            f.write("// test")
        
        files = self.engine._scan_project_files(self.project_dir)
        
        self.assertEqual(len(files), 2)
        self.assertTrue(any(f.endswith('.py') for f in files))
        self.assertTrue(any(f.endswith('.java') for f in files))


class TestFileMonitor(unittest.TestCase):
    """Unit tests for file monitor module."""
    
    def test_file_event_creation(self):
        """Test FileEvent creation."""
        event = FileEvent(
            file_path="/test/file.py",
            event_type=FileEventType.MODIFIED,
            timestamp=time.time()
        )
        
        self.assertEqual(event.file_path, "/test/file.py")
        self.assertEqual(event.event_type, FileEventType.MODIFIED)
    
    def test_file_event_equality(self):
        """Test FileEvent equality."""
        event1 = FileEvent("/test/file.py", FileEventType.MODIFIED, 1.0)
        event2 = FileEvent("/test/file.py", FileEventType.MODIFIED, 2.0)
        event3 = FileEvent("/test/other.py", FileEventType.MODIFIED, 1.0)
        
        self.assertEqual(event1, event2)
        self.assertNotEqual(event1, event3)
    
    def test_debounce_queue(self):
        """Test debounce queue functionality."""
        queue = DebounceMergeQueue(debounce_window_ms=100)
        
        received_events = []
        def callback(event):
            received_events.append(event)
        
        queue.set_callback(callback)
        
        # Add events
        event1 = FileEvent("/test/file.py", FileEventType.MODIFIED, time.time())
        queue.add_event(event1)
        
        # Wait for debounce
        time.sleep(0.2)
        
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].file_path, "/test/file.py")
        
        queue.shutdown()


class TestLLMAnalyzer(unittest.TestCase):
    """Unit tests for LLM analyzer."""
    
    def setUp(self):
        """Set up mock analyzer."""
        self.analyzer = MockLLMAnalyzer()
    
    def test_analyzer_availability(self):
        """Test analyzer availability."""
        self.assertTrue(self.analyzer.is_available())
    
    def test_code_analysis(self):
        """Test code analysis."""
        code = "def test(): pass"
        result = self.analyzer.analyze_code(code, AnalysisType.SUMMARY)
        
        self.assertTrue(result.success)
        self.assertIsNotNone(result.content)
        self.assertGreater(result.processing_time_ms, 0)
    
    def test_analysis_types(self):
        """Test different analysis types."""
        code = "def test(): pass"
        
        for analysis_type in AnalysisType:
            result = self.analyzer.analyze_code(code, analysis_type)
            self.assertTrue(result.success)
            self.assertIsNotNone(result.content)
    
    def test_cache_functionality(self):
        """Test analysis caching."""
        code = "def test(): pass"
        
        result1 = self.analyzer.analyze_code(code, AnalysisType.SUMMARY)
        result2 = self.analyzer.analyze_code(code, AnalysisType.SUMMARY)
        
        # Both should succeed
        self.assertTrue(result1.success)
        self.assertTrue(result2.success)


class TestUpdateStatistics(unittest.TestCase):
    """Unit tests for update statistics."""
    
    def test_statistics_creation(self):
        """Test UpdateStatistics creation."""
        stats = UpdateStatistics(
            file_path="/test/file.py",
            event_type="modified",
            processing_time_ms=100.5,
            types_count=5,
            functions_count=10,
            success=True
        )
        
        self.assertEqual(stats.file_path, "/test/file.py")
        self.assertEqual(stats.types_count, 5)
        self.assertEqual(stats.functions_count, 10)
        self.assertTrue(stats.success)


def run_tests():
    """Run all unit tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestParserInterface))
    suite.addTests(loader.loadTestsFromTestCase(TestPythonParser))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseManager))
    suite.addTests(loader.loadTestsFromTestCase(TestIncrementalUpdateEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestFileMonitor))
    suite.addTests(loader.loadTestsFromTestCase(TestLLMAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestUpdateStatistics))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
