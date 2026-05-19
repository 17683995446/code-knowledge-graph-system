"""
Web Server Module
Flask-based REST API and WebSocket server for the knowledge graph visualization.
"""

import os
import json
import time
from typing import Dict, Any, Optional
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS

# Import system modules
from database_schema import DatabaseManager
from incremental_update_engine import IncrementalUpdateEngine
from file_monitor_module import FileMonitor, FileEvent, FileEventType
from llm_analyzer import create_analyzer, AnalysisType
from architecture_diagram import (
    generate_system_architecture_svg,
    generate_flowchart_svg,
    generate_sequence_diagram_svg,
    generate_data_model_svg,
    generate_performance_chart_svg
)


class KnowledgeGraphServer:
    """Web server for the code knowledge graph system."""
    
    def __init__(self, project_path: str, database_path: str, 
                 api_key: Optional[str] = None, host: str = '0.0.0.0', port: int = 5000,
                 db_manager: Optional[DatabaseManager] = None,
                 update_engine: Optional[IncrementalUpdateEngine] = None):
        self.project_path = os.path.abspath(project_path)
        self.database_path = database_path
        self.host = host
        self.port = port
        
        # Use provided components or create new ones (backward compatible)
        self.db_manager = db_manager if db_manager is not None else DatabaseManager(database_path)
        self.update_engine = update_engine if update_engine is not None else IncrementalUpdateEngine(self.db_manager)
        self.file_monitor: Optional[FileMonitor] = None
        self.llm_analyzer = create_analyzer(api_key, use_mock=(api_key is None))
        
        # Create Flask app
        self.app = Flask(__name__, static_folder='static')
        CORS(self.app)
        
        # Register teardown to close DB connections after each request
        @self.app.teardown_request
        def close_db_connection(exception=None):
            """Close the database connection for the current request thread."""
            try:
                self.db_manager.close()
            except Exception:
                pass
        
        # Register routes
        self._register_routes()
        
        # Statistics
        self.start_time = time.time()
        self.update_count = 0
    
    def _register_routes(self):
        """Register all API routes."""
        
        # Static files
        @self.app.route('/')
        def index():
            return self._render_dashboard()
        
        @self.app.route('/static/<path:filename>')
        def static_files(filename):
            return send_from_directory('static', filename)
        
        # API Routes
        @self.app.route('/api/status')
        def api_status():
            return jsonify(self._get_system_status())
        
        @self.app.route('/api/statistics')
        def api_statistics():
            return jsonify(self._get_database_statistics())
        
        @self.app.route('/api/files')
        def api_files():
            language = request.args.get('language')
            return jsonify(self._get_files(language))
        
        @self.app.route('/api/files/<int:file_id>')
        def api_file_detail(file_id):
            return jsonify(self._get_file_detail(file_id))
        
        @self.app.route('/api/types')
        def api_types():
            file_id = request.args.get('file_id', type=int)
            return jsonify(self._get_types(file_id))
        
        @self.app.route('/api/functions')
        def api_functions():
            type_id = request.args.get('type_id', type=int)
            file_id = request.args.get('file_id', type=int)
            return jsonify(self._get_functions(type_id, file_id))
        
        @self.app.route('/api/calls')
        def api_calls():
            function_id = request.args.get('function_id', type=int)
            return jsonify(self._get_calls(function_id))
        
        @self.app.route('/api/references')
        def api_references():
            type_id = request.args.get('type_id', type=int)
            return jsonify(self._get_references(type_id))
        
        @self.app.route('/api/graph')
        def api_graph():
            return jsonify(self._get_knowledge_graph())
        
        @self.app.route('/api/sync', methods=['POST'])
        def api_sync():
            return jsonify(self._perform_full_sync())
        
        @self.app.route('/api/analyze/<int:file_id>')
        def api_analyze_file(file_id):
            analysis_type = request.args.get('type', 'summary')
            return jsonify(self._analyze_file(file_id, analysis_type))
        
        @self.app.route('/api/diagrams/<diagram_name>')
        def api_diagram(diagram_name):
            return self._get_diagram(diagram_name)
        
        @self.app.route('/api/updates/recent')
        def api_recent_updates():
            count = request.args.get('count', 10, type=int)
            return jsonify(self._get_recent_updates(count))
        
        @self.app.route('/api/search')
        def api_search():
            query = request.args.get('q', '')
            return jsonify(self._search(query))
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        uptime = time.time() - self.start_time
        return {
            'status': 'running',
            'project_path': self.project_path,
            'database_path': self.database_path,
            'uptime_seconds': int(uptime),
            'monitoring_active': self.file_monitor is not None and self.file_monitor.is_running,
            'llm_available': self.llm_analyzer.is_available(),
            'update_count': self.update_count,
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_database_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        self.db_manager.connect()
        
        stats = self.db_manager.get_statistics()
        file_stats = self.db_manager.get_file_statistics()
        
        # Get language distribution
        languages = []
        for lang, count in file_stats.items():
            languages.append({'language': lang, 'count': count})
        
        return {
            'total_files': stats.get('files', 0),
            'total_types': stats.get('types', 0),
            'total_functions': stats.get('functions', 0),
            'total_calls': stats.get('calls', 0),
            'total_references': stats.get('relationships', 0),
            'languages': languages
        }
    
    def _get_files(self, language: Optional[str] = None) -> Dict[str, Any]:
        """Get list of files."""
        self.db_manager.connect()
        
        if language:
            results = self.db_manager.execute_query(
                "SELECT id, path, language, modified FROM files WHERE language = ?",
                (language,)
            )
        else:
            results = self.db_manager.execute_query(
                "SELECT id, path, language, modified FROM files"
            )
        
        files = []
        for row in results:
            files.append({
                'id': row[0],
                'path': row[1],
                'language': row[2],
                'modified': row[3]
            })
        
        return {'files': files, 'count': len(files)}
    
    def _get_file_detail(self, file_id: int) -> Dict[str, Any]:
        """Get detailed information about a file."""
        self.db_manager.connect()
        
        file_info = self.db_manager.execute_query(
            "SELECT id, path, language, hash, modified FROM files WHERE id = ?",
            (file_id,)
        )
        
        if not file_info:
            return {'error': 'File not found'}
        
        row = file_info[0]
        return {
            'id': row[0],
            'path': row[1],
            'language': row[2],
            'hash': row[3].hex() if row[3] else None,
            'modified': row[4]
        }
    
    def _get_types(self, file_id: Optional[int] = None) -> Dict[str, Any]:
        """Get types (classes, interfaces, etc.)."""
        self.db_manager.connect()
        
        if file_id:
            results = self.db_manager.execute_query(
                """SELECT t.id, t.name, t.kind, t.flags, t.line_start, t.line_end, f.path
                   FROM types t JOIN files f ON t.file_id = f.id WHERE t.file_id = ?""",
                (file_id,)
            )
        else:
            results = self.db_manager.execute_query(
                """SELECT t.id, t.name, t.kind, t.flags, t.line_start, t.line_end, f.path
                   FROM types t JOIN files f ON t.file_id = f.id"""
            )
        
        types = []
        for row in results:
            types.append({
                'id': row[0],
                'name': row[1],
                'kind': row[2],
                'flags': row[3],
                'line_start': row[4],
                'line_end': row[5],
                'file_path': row[6]
            })
        
        return {'types': types, 'count': len(types)}
    
    def _get_functions(self, type_id: Optional[int] = None, 
                       file_id: Optional[int] = None) -> Dict[str, Any]:
        """Get functions/methods."""
        self.db_manager.connect()
        
        if type_id:
            results = self.db_manager.execute_query(
                """SELECT f.id, f.name, f.signature, f.line_start, f.line_end, 
                          t.name as type_name, fl.path
                   FROM functions f 
                   LEFT JOIN types t ON f.type_id = t.id
                   JOIN files fl ON f.file_id = fl.id
                   WHERE f.type_id = ?""",
                (type_id,)
            )
        elif file_id:
            results = self.db_manager.execute_query(
                """SELECT f.id, f.name, f.signature, f.line_start, f.line_end, 
                          t.name as type_name, fl.path
                   FROM functions f 
                   LEFT JOIN types t ON f.type_id = t.id
                   JOIN files fl ON f.file_id = fl.id
                   WHERE f.file_id = ?""",
                (file_id,)
            )
        else:
            results = self.db_manager.execute_query(
                """SELECT f.id, f.name, f.signature, f.line_start, f.line_end, 
                          t.name as type_name, fl.path
                   FROM functions f 
                   LEFT JOIN types t ON f.type_id = t.id
                   JOIN files fl ON f.file_id = fl.id"""
            )
        
        functions = []
        for row in results:
            functions.append({
                'id': row[0],
                'name': row[1],
                'signature': row[2],
                'line_start': row[3],
                'line_end': row[4],
                'type_name': row[5],
                'file_path': row[6]
            })
        
        return {'functions': functions, 'count': len(functions)}
    
    def _get_calls(self, function_id: Optional[int] = None) -> Dict[str, Any]:
        """Get function call relationships."""
        self.db_manager.connect()
        
        if function_id:
            # Get calls from this function
            outgoing = self.db_manager.execute_query(
                """SELECT c.caller_id, c.callee_id, c.line_number,
                          cf.name as caller_name, ct.name as callee_name
                   FROM calls c
                   JOIN functions cf ON c.caller_id = cf.id
                   JOIN functions ct ON c.callee_id = ct.id
                   WHERE c.caller_id = ?""",
                (function_id,)
            )
            
            # Get calls to this function
            incoming = self.db_manager.execute_query(
                """SELECT c.caller_id, c.callee_id, c.line_number,
                          cf.name as caller_name, ct.name as callee_name
                   FROM calls c
                   JOIN functions cf ON c.caller_id = cf.id
                   JOIN functions ct ON c.callee_id = ct.id
                   WHERE c.callee_id = ?""",
                (function_id,)
            )
            
            return {
                'outgoing': [{'caller_id': r[0], 'callee_id': r[1], 'line': r[2],
                             'caller_name': r[3], 'callee_name': r[4]} for r in outgoing],
                'incoming': [{'caller_id': r[0], 'callee_id': r[1], 'line': r[2],
                             'caller_name': r[3], 'callee_name': r[4]} for r in incoming]
            }
        else:
            results = self.db_manager.execute_query(
                """SELECT c.caller_id, c.callee_id, c.line_number,
                          cf.name as caller_name, ct.name as callee_name
                   FROM calls c
                   JOIN functions cf ON c.caller_id = cf.id
                   JOIN functions ct ON c.callee_id = ct.id
                   LIMIT 1000"""
            )
            
            calls = []
            for row in results:
                calls.append({
                    'caller_id': row[0],
                    'callee_id': row[1],
                    'line': row[2],
                    'caller_name': row[3],
                    'callee_name': row[4]
                })
            
            return {'calls': calls, 'count': len(calls)}
    
    def _get_references(self, type_id: Optional[int] = None) -> Dict[str, Any]:
        """Get reference relationships."""
        self.db_manager.connect()
        
        if type_id:
            outgoing = self.db_manager.execute_query(
                """SELECT r.from_id, r.to_id, r.kind, r.line_number,
                          tf.name as from_name, tt.name as to_name
                   FROM relationships r
                   JOIN types tf ON r.from_id = tf.id
                   JOIN types tt ON r.to_id = tt.id
                   WHERE r.from_id = ?""",
                (type_id,)
            )
            
            incoming = self.db_manager.execute_query(
                """SELECT r.from_id, r.to_id, r.kind, r.line_number,
                          tf.name as from_name, tt.name as to_name
                   FROM relationships r
                   JOIN types tf ON r.from_id = tf.id
                   JOIN types tt ON r.to_id = tt.id
                   WHERE r.to_id = ?""",
                (type_id,)
            )
            
            return {
                'outgoing': [{'from_id': r[0], 'to_id': r[1], 'kind': r[2], 'line': r[3],
                             'from_name': r[4], 'to_name': r[5]} for r in outgoing],
                'incoming': [{'from_id': r[0], 'to_id': r[1], 'kind': r[2], 'line': r[3],
                             'from_name': r[4], 'to_name': r[5]} for r in incoming]
            }
        else:
            results = self.db_manager.execute_query(
                """SELECT r.from_id, r.to_id, r.kind, r.line_number,
                          tf.name as from_name, tt.name as to_name
                   FROM relationships r
                   JOIN types tf ON r.from_id = tf.id
                   JOIN types tt ON r.to_id = tt.id
                   LIMIT 1000"""
            )
            
            refs = []
            for row in results:
                refs.append({
                    'from_id': row[0],
                    'to_id': row[1],
                    'kind': row[2],
                    'line': row[3],
                    'from_name': row[4],
                    'to_name': row[5]
                })
            
            return {'references': refs, 'count': len(refs)}
    
    def _get_knowledge_graph(self) -> Dict[str, Any]:
        """Get complete knowledge graph for visualization."""
        self.db_manager.connect()
        
        # Get all nodes (types and functions)
        type_nodes = self.db_manager.execute_query(
            "SELECT id, name, kind FROM types"
        )
        
        func_nodes = self.db_manager.execute_query(
            "SELECT id, name FROM functions"
        )
        
        # Get all edges (calls and references)
        call_edges = self.db_manager.execute_query(
            "SELECT caller_id, callee_id FROM calls"
        )
        
        ref_edges = self.db_manager.execute_query(
            "SELECT from_id, to_id, kind FROM relationships"
        )
        
        nodes = []
        for row in type_nodes:
            nodes.append({'id': f'type_{row[0]}', 'name': row[1], 'type': row[2]})
        
        for row in func_nodes:
            nodes.append({'id': f'func_{row[0]}', 'name': row[1], 'type': 'function'})
        
        edges = []
        for row in call_edges:
            edges.append({
                'source': f'func_{row[0]}',
                'target': f'func_{row[1]}',
                'type': 'call'
            })
        
        for row in ref_edges:
            edges.append({
                'source': f'type_{row[0]}',
                'target': f'type_{row[1]}',
                'type': row[2]
            })
        
        return {'nodes': nodes, 'edges': edges}
    
    def _perform_full_sync(self) -> Dict[str, Any]:
        """Perform full project synchronization."""
        result = self.update_engine.perform_full_sync(self.project_path)
        self.update_count += result.get('files_updated', 0) + result.get('files_deleted', 0)
        return result
    
    def _analyze_file(self, file_id: int, analysis_type: str) -> Dict[str, Any]:
        """Analyze a file using LLM."""
        self.db_manager.connect()
        
        # Get file info
        file_info = self.db_manager.execute_query(
            "SELECT path FROM files WHERE id = ?",
            (file_id,)
        )
        
        if not file_info:
            return {'error': 'File not found'}
        
        file_path = file_info[0][0]
        
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return {'error': f'Cannot read file: {e}'}
        
        # Perform analysis
        try:
            analysis_enum = AnalysisType(analysis_type)
        except ValueError:
            analysis_enum = AnalysisType.SUMMARY
        
        result = self.llm_analyzer.analyze_code(content, analysis_enum)
        
        return {
            'file_id': file_id,
            'file_path': file_path,
            'analysis_type': analysis_type,
            'content': result.content if result.success else None,
            'success': result.success,
            'processing_time_ms': result.processing_time_ms
        }
    
    def _get_diagram(self, diagram_name: str):
        """Get SVG diagram."""
        generators = {
            'architecture': generate_system_architecture_svg,
            'flowchart': generate_flowchart_svg,
            'sequence': generate_sequence_diagram_svg,
            'database': generate_data_model_svg,
            'performance': generate_performance_chart_svg
        }
        
        generator = generators.get(diagram_name)
        if generator:
            svg_content = generator()
            return svg_content, 200, {'Content-Type': 'image/svg+xml'}
        
        return jsonify({'error': 'Diagram not found'}), 404
    
    def _get_recent_updates(self, count: int) -> Dict[str, Any]:
        """Get recent file updates."""
        self.db_manager.connect()
        
        results = self.db_manager.execute_query(
            """SELECT file_path, event_type, processed_at, processing_time_ms
               FROM change_log ORDER BY processed_at DESC LIMIT ?""",
            (count,)
        )
        
        updates = []
        for row in results:
            updates.append({
                'file_path': row[0],
                'event_type': row[1],
                'processed_at': row[2],
                'processing_time_ms': row[3]
            })
        
        return {'updates': updates, 'count': len(updates)}
    
    @staticmethod
    def _escape_like_pattern(pattern: str) -> str:
        """Escape SQL LIKE wildcards in a search pattern."""
        return pattern.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    def _search(self, query: str) -> Dict[str, Any]:
        """Search across all entities."""
        self.db_manager.connect()
        
        search_pattern = f'%{self._escape_like_pattern(query)}%'
        
        # Search files
        files = self.db_manager.execute_query(
            "SELECT id, path, language FROM files WHERE path LIKE ? ESCAPE '\\'",
            (search_pattern,)
        )
        
        # Search types
        types = self.db_manager.execute_query(
            "SELECT id, name, kind FROM types WHERE name LIKE ? ESCAPE '\\'",
            (search_pattern,)
        )
        
        # Search functions
        functions = self.db_manager.execute_query(
            "SELECT id, name FROM functions WHERE name LIKE ? ESCAPE '\\'",
            (search_pattern,)
        )
        
        return {
            'files': [{'id': r[0], 'path': r[1], 'language': r[2]} for r in files],
            'types': [{'id': r[0], 'name': r[1], 'kind': r[2]} for r in types],
            'functions': [{'id': r[0], 'name': r[1]} for r in functions]
        }
    
    def _render_dashboard(self) -> str:
        """Render the main dashboard HTML."""
        return render_template_string(HTML_TEMPLATE)
    
    def start_monitoring(self):
        """Start file monitoring."""
        if self.file_monitor is None:
            self.file_monitor = FileMonitor(self.project_path)
            
            def on_file_event(event: FileEvent):
                result = self.update_engine.process_file_event(event)
                if result.success:
                    self.update_count += 1
            
            self.file_monitor.set_event_callback(on_file_event)
            self.file_monitor.start()
    
    def stop_monitoring(self):
        """Stop file monitoring."""
        if self.file_monitor:
            self.file_monitor.stop()
            self.file_monitor = None
    
    def run(self, debug: bool = False):
        """Run the web server."""
        # Initialize database
        self.db_manager.initialize_schema()
        
        # Start monitoring
        self.start_monitoring()
        
        try:
            print(f"Starting server at http://{self.host}:{self.port}")
            print(f"Project path: {self.project_path}")
            self.app.run(host=self.host, port=self.port, debug=debug)
        finally:
            self.stop_monitoring()
            self.db_manager.close()


# HTML Template for the dashboard
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Knowledge Graph</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .header { background: #1a1a2e; color: white; padding: 1rem 2rem; }
        .header h1 { font-size: 1.5rem; font-weight: 500; }
        .container { max-width: 1400px; margin: 0 auto; padding: 2rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .stat-card .label { color: #666; font-size: 0.875rem; margin-bottom: 0.5rem; }
        .stat-card .value { font-size: 2rem; font-weight: 600; color: #1a1a2e; }
        .section { background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .section h2 { font-size: 1.25rem; margin-bottom: 1rem; color: #1a1a2e; }
        .tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; border-bottom: 1px solid #e0e0e0; }
        .tab { padding: 0.75rem 1rem; cursor: pointer; border-bottom: 2px solid transparent; }
        .tab.active { border-bottom-color: #3b82f6; color: #3b82f6; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid #e0e0e0; }
        th { font-weight: 500; color: #666; font-size: 0.875rem; }
        .btn { background: #3b82f6; color: white; padding: 0.5rem 1rem; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #2563eb; }
        #graph-container { width: 100%; height: 500px; border: 1px solid #e0e0e0; border-radius: 4px; }
        .status-badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; }
        .status-running { background: #dcfce7; color: #166534; }
        .status-stopped { background: #fee2e2; color: #991b1b; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Code Knowledge Graph System</h1>
    </div>
    
    <div class="container">
        <div class="stats-grid" id="stats">
            <div class="stat-card">
                <div class="label">Total Files</div>
                <div class="value" id="total-files">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Types</div>
                <div class="value" id="total-types">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Functions</div>
                <div class="value" id="total-functions">-</div>
            </div>
            <div class="stat-card">
                <div class="label">Call Relations</div>
                <div class="value" id="total-calls">-</div>
            </div>
        </div>
        
        <div class="section">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h2>System Status</h2>
                <button class="btn" onclick="performSync()">Full Sync</button>
            </div>
            <div id="status-info" style="margin-top:1rem;">
                <p>Loading...</p>
            </div>
        </div>
        
        <div class="section">
            <h2>Knowledge Graph Visualization</h2>
            <div id="graph-container"></div>
        </div>
        
        <div class="section">
            <div class="tabs">
                <div class="tab active" onclick="showTab('files')">Files</div>
                <div class="tab" onclick="showTab('types')">Types</div>
                <div class="tab" onclick="showTab('functions')">Functions</div>
                <div class="tab" onclick="showTab('diagrams')">Diagrams</div>
            </div>
            
            <div id="files" class="tab-content active">
                <table>
                    <thead>
                        <tr><th>Path</th><th>Language</th><th>Modified</th></tr>
                    </thead>
                    <tbody id="files-table"></tbody>
                </table>
            </div>
            
            <div id="types" class="tab-content">
                <table>
                    <thead>
                        <tr><th>Name</th><th>Kind</th><th>File</th></tr>
                    </thead>
                    <tbody id="types-table"></tbody>
                </table>
            </div>
            
            <div id="functions" class="tab-content">
                <table>
                    <thead>
                        <tr><th>Name</th><th>Type</th><th>File</th></tr>
                    </thead>
                    <tbody id="functions-table"></tbody>
                </table>
            </div>
            
            <div id="diagrams" class="tab-content">
                <div style="display:grid; gap:1rem;">
                    <div>
                        <h3>System Architecture</h3>
                        <img src="/api/diagrams/architecture" style="max-width:100%; border:1px solid #e0e0e0; border-radius:4px;">
                    </div>
                    <div>
                        <h3>System Flowchart</h3>
                        <img src="/api/diagrams/flowchart" style="max-width:100%; border:1px solid #e0e0e0; border-radius:4px;">
                    </div>
                    <div>
                        <h3>Database Schema</h3>
                        <img src="/api/diagrams/database" style="max-width:100%; border:1px solid #e0e0e0; border-radius:4px;">
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Load statistics
        async function loadStats() {
            const res = await fetch('/api/statistics');
            const data = await res.json();
            document.getElementById('total-files').textContent = data.total_files || 0;
            document.getElementById('total-types').textContent = data.total_types || 0;
            document.getElementById('total-functions').textContent = data.total_functions || 0;
            document.getElementById('total-calls').textContent = data.total_calls || 0;
        }
        
        // Load status
        async function loadStatus() {
            const res = await fetch('/api/status');
            const data = await res.json();
            const statusHtml = `
                <p><strong>Status:</strong> <span class="status-badge ${data.monitoring_active ? 'status-running' : 'status-stopped'}">${data.monitoring_active ? 'Running' : 'Stopped'}</span></p>
                <p><strong>Project:</strong> ${data.project_path}</p>
                <p><strong>Uptime:</strong> ${Math.floor(data.uptime_seconds / 60)}m ${data.uptime_seconds % 60}s</p>
                <p><strong>Updates:</strong> ${data.update_count}</p>
                <p><strong>LLM Available:</strong> ${data.llm_available ? 'Yes' : 'No'}</p>
            `;
            document.getElementById('status-info').innerHTML = statusHtml;
        }
        
        // Load files
        async function loadFiles() {
            const res = await fetch('/api/files');
            const data = await res.json();
            const tbody = document.getElementById('files-table');
            tbody.innerHTML = data.files.slice(0, 50).map(f => `
                <tr>
                    <td>${f.path}</td>
                    <td>${f.language}</td>
                    <td>${new Date(f.modified * 1000).toLocaleString()}</td>
                </tr>
            `).join('');
        }
        
        // Load types
        async function loadTypes() {
            const res = await fetch('/api/types');
            const data = await res.json();
            const tbody = document.getElementById('types-table');
            tbody.innerHTML = data.types.slice(0, 50).map(t => `
                <tr>
                    <td>${t.name}</td>
                    <td>${t.kind}</td>
                    <td>${t.file_path}</td>
                </tr>
            `).join('');
        }
        
        // Load functions
        async function loadFunctions() {
            const res = await fetch('/api/functions');
            const data = await res.json();
            const tbody = document.getElementById('functions-table');
            tbody.innerHTML = data.functions.slice(0, 50).map(f => `
                <tr>
                    <td>${f.name}</td>
                    <td>${f.type_name || '-'}</td>
                    <td>${f.file_path}</td>
                </tr>
            `).join('');
        }
        
        // Perform sync
        async function performSync() {
            const btn = document.querySelector('.btn');
            btn.textContent = 'Syncing...';
            btn.disabled = true;
            const res = await fetch('/api/sync', { method: 'POST' });
            const data = await res.json();
            alert(`Sync complete! Updated: ${data.files_updated}, Deleted: ${data.files_deleted}`);
            btn.textContent = 'Full Sync';
            btn.disabled = false;
            loadStats();
        }
        
        // Tab switching
        function showTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
        }
        
        // Draw graph
        async function drawGraph() {
            const res = await fetch('/api/graph');
            const data = await res.json();
            
            if (data.nodes.length === 0) return;
            
            const container = document.getElementById('graph-container');
            const width = container.clientWidth;
            const height = 500;
            
            const svg = d3.select('#graph-container')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            const simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.edges).id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2));
            
            const link = svg.append('g')
                .selectAll('line')
                .data(data.edges)
                .enter().append('line')
                .attr('stroke', '#999')
                .attr('stroke-opacity', 0.6)
                .attr('stroke-width', 1);
            
            const node = svg.append('g')
                .selectAll('circle')
                .data(data.nodes)
                .enter().append('circle')
                .attr('r', d => d.type === 'function' ? 5 : 8)
                .attr('fill', d => d.type === 'function' ? '#3b82f6' : '#10b981')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));
            
            const label = svg.append('g')
                .selectAll('text')
                .data(data.nodes)
                .enter().append('text')
                .text(d => d.name)
                .attr('font-size', '10px')
                .attr('dx', 10)
                .attr('dy', 3);
            
            simulation.on('tick', () => {
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);
                
                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);
                
                label
                    .attr('x', d => d.x)
                    .attr('y', d => d.y);
            });
            
            function dragstarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }
            
            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }
            
            function dragended(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
        }
        
        // Initialize
        loadStats();
        loadStatus();
        loadFiles();
        loadTypes();
        loadFunctions();
        drawGraph();
        
        // Auto-refresh every 5 seconds
        setInterval(() => {
            loadStats();
            loadStatus();
        }, 5000);
    </script>
</body>
</html>
'''


if __name__ == '__main__':
    import sys
    
    project_path = sys.argv[1] if len(sys.argv) > 1 else '/data/user/work/code_knowledge_graph_system'
    database_path = '/data/user/work/code_knowledge_graph_system/data/knowledge_graph.db'
    api_key = os.environ.get('SILICON_FLOW_API_KEY')
    
    server = KnowledgeGraphServer(project_path, database_path, api_key)
    server.run(debug=True)
