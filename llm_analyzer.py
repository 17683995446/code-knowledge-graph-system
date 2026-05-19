"""
LLM Analysis Module
Integrates with Silicon Flow API for code analysis and insights.
Uses the free model provided by Silicon Flow.
"""

import os
import json
import hashlib
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from collections import OrderedDict

# Try to import requests, provide fallback if not available
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class AnalysisType(Enum):
    """Types of code analysis supported."""
    SUMMARY = "summary"
    COMPLEXITY = "complexity"
    DEPENDENCIES = "dependencies"
    SUGGESTIONS = "suggestions"
    SECURITY = "security"


@dataclass
class AnalysisResult:
    """Result of LLM analysis."""
    analysis_type: AnalysisType
    content: str
    confidence: float
    processing_time_ms: float
    timestamp: float
    success: bool
    error_message: Optional[str] = None


class LLMCodeAnalyzer:
    """
    Code analyzer using Silicon Flow LLM API.
    Provides intelligent code analysis and insights.
    """
    
    API_BASE_URL = "https://api.siliconflow.cn/v1"
    DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"  # Free model
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the LLM analyzer.
        
        Args:
            api_key: Silicon Flow API key. If not provided, will try to get from environment.
        """
        self.api_key = api_key or os.environ.get('SILICON_FLOW_API_KEY')
        self.model = self.DEFAULT_MODEL
        self.request_timeout = 30  # seconds
        self.cache: OrderedDict[str, AnalysisResult] = OrderedDict()  # LRU cache
        self.cache_ttl = 300  # 5 minutes cache
        self.max_cache_size = 1000  # Maximum cache entries to prevent memory leak
    
    def is_available(self) -> bool:
        """Check if LLM service is available."""
        return REQUESTS_AVAILABLE and self.api_key is not None
    
    def _make_api_request(self, messages: List[Dict[str, str]], 
                          temperature: float = 0.3) -> Optional[Dict[str, Any]]:
        """Make API request to Silicon Flow."""
        if not self.is_available():
            return None
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 2048,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.API_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.request_timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as error:
            print(f"LLM API request failed: {error}")
            return None
    
    def analyze_code(self, code: str, analysis_type: AnalysisType,
                     context: Optional[str] = None) -> AnalysisResult:
        """
        Analyze code using LLM.
        
        Args:
            code: Source code to analyze
            analysis_type: Type of analysis to perform
            context: Optional context about the code
        
        Returns:
            AnalysisResult with the analysis content
        """
        start_time = time.time()
        
        # Check cache
        cache_key = f"{hashlib.md5(code.encode('utf-8')).hexdigest()}_{analysis_type.value}"
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            if time.time() - cached.timestamp < self.cache_ttl:
                # Move to end (most recently used)
                self.cache.move_to_end(cache_key)
                return cached
            else:
                # Expired, remove it
                del self.cache[cache_key]
        
        # Build prompt based on analysis type
        prompt = self._build_analysis_prompt(code, analysis_type, context)
        
        messages = [
            {"role": "system", "content": "You are an expert code analyst. Provide concise, accurate analysis."},
            {"role": "user", "content": prompt}
        ]
        
        response = self._make_api_request(messages)
        
        processing_time = (time.time() - start_time) * 1000
        
        if response and 'choices' in response and len(response['choices']) > 0:
            content = response['choices'][0]['message']['content']
            result = AnalysisResult(
                analysis_type=analysis_type,
                content=content,
                confidence=0.85,  # Default confidence
                processing_time_ms=processing_time,
                timestamp=time.time(),
                success=True
            )
        else:
            result = AnalysisResult(
                analysis_type=analysis_type,
                content="",
                confidence=0.0,
                processing_time_ms=processing_time,
                timestamp=time.time(),
                success=False,
                error_message="Failed to get response from LLM API"
            )
        
        # Cache successful results with LRU eviction
        if result.success:
            # Evict oldest entries if cache is full
            while len(self.cache) >= self.max_cache_size:
                self.cache.popitem(last=False)  # Remove oldest (FIFO)
            self.cache[cache_key] = result
        
        return result
    
    def _build_analysis_prompt(self, code: str, analysis_type: AnalysisType,
                               context: Optional[str]) -> str:
        """Build the analysis prompt based on type."""
        base_context = f"Context: {context}\n\n" if context else ""
        
        prompts = {
            AnalysisType.SUMMARY: f"""{base_context}Analyze the following code and provide a brief summary (2-3 sentences) of what it does, its main purpose, and key functionality:

```
{code}
```

Summary:""",
            
            AnalysisType.COMPLEXITY: f"""{base_context}Analyze the complexity of the following code. Rate cyclomatic complexity (1-10), identify complex functions, and suggest simplifications:

```
{code}
```

Complexity Analysis:""",
            
            AnalysisType.DEPENDENCIES: f"""{base_context}Identify all external dependencies, imports, and relationships in this code. List what modules/classes/functions it depends on:

```
{code}
```

Dependencies:""",
            
            AnalysisType.SUGGESTIONS: f"""{base_context}Review the following code and provide 2-3 specific suggestions for improvement (performance, readability, best practices):

```
{code}
```

Suggestions:""",
            
            AnalysisType.SECURITY: f"""{base_context}Analyze the following code for potential security issues. Identify any vulnerabilities, unsafe practices, or areas that need attention:

```
{code}
```

Security Analysis:"""
        }
        
        return prompts.get(analysis_type, prompts[AnalysisType.SUMMARY])
    
    def analyze_file_structure(self, file_path: str, code: str) -> Dict[str, Any]:
        """Analyze file structure and return structured information."""
        result = {
            'file_path': file_path,
            'analysis': {}
        }
        
        # Get summary
        summary = self.analyze_code(code, AnalysisType.SUMMARY)
        if summary.success:
            result['analysis']['summary'] = summary.content
        
        # Get complexity
        complexity = self.analyze_code(code, AnalysisType.COMPLEXITY)
        if complexity.success:
            result['analysis']['complexity'] = complexity.content
        
        # Get suggestions
        suggestions = self.analyze_code(code, AnalysisType.SUGGESTIONS)
        if suggestions.success:
            result['analysis']['suggestions'] = suggestions.content
        
        return result
    
    def generate_architecture_insights(self, project_stats: Dict[str, Any]) -> str:
        """Generate insights about project architecture."""
        if not self.is_available():
            return "LLM analysis not available"
        
        prompt = f"""Given the following project statistics, provide insights about the architecture and organization:

Project Statistics:
- Total Files: {project_stats.get('total_files', 0)}
- Languages: {project_stats.get('languages', {})}
- Total Types (Classes/Interfaces): {project_stats.get('total_types', 0)}
- Total Functions: {project_stats.get('total_functions', 0)}
- Total Call Relationships: {project_stats.get('total_calls', 0)}
- Total References: {project_stats.get('total_references', 0)}

Architecture Insights:"""
        
        messages = [
            {"role": "system", "content": "You are a software architecture expert."},
            {"role": "user", "content": prompt}
        ]
        
        response = self._make_api_request(messages, temperature=0.5)
        
        if response and 'choices' in response:
            return response['choices'][0]['message']['content']
        
        return "Unable to generate architecture insights"
    
    def clear_cache(self):
        """Clear the analysis cache."""
        self.cache.clear()


class MockLLMAnalyzer(LLMCodeAnalyzer):
    """Mock analyzer for testing without API access."""
    
    def __init__(self):
        super().__init__(api_key="mock")
    
    def is_available(self) -> bool:
        """Always available for testing."""
        return True
    
    def _make_api_request(self, messages: List[Dict[str, str]], 
                          temperature: float = 0.3) -> Optional[Dict[str, Any]]:
        """Return mock response."""
        content = messages[1]['content'] if len(messages) > 1 else ""
        
        # Generate mock analysis based on content
        if "summary" in content.lower():
            response_text = "This code appears to be a Python module defining classes and functions for data processing."
        elif "complexity" in content.lower():
            response_text = "Cyclomatic complexity: 5/10. The code has moderate complexity with some nested conditionals that could be simplified."
        elif "depend" in content.lower():
            response_text = "Dependencies: os, sys, typing, dataclasses. No external library dependencies detected."
        elif "suggestion" in content.lower():
            response_text = "1. Add type hints to all function parameters. 2. Consider breaking down large functions. 3. Add docstrings for better documentation."
        elif "security" in content.lower():
            response_text = "No obvious security issues detected. Consider adding input validation for user-provided paths."
        else:
            response_text = "Analysis complete. Code structure looks reasonable."
        
        return {
            "choices": [{
                "message": {"content": response_text}
            }]
        }


def create_analyzer(api_key: Optional[str] = None, use_mock: bool = False) -> LLMCodeAnalyzer:
    """Factory function to create appropriate analyzer."""
    if use_mock:
        return MockLLMAnalyzer()
    
    analyzer = LLMCodeAnalyzer(api_key)
    if not analyzer.is_available():
        print("Warning: LLM API not available, using mock analyzer")
        return MockLLMAnalyzer()
    
    return analyzer


if __name__ == '__main__':
    # Test the analyzer
    test_code = '''
def calculate_factorial(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0 or n == 1:
        return 1
    return n * calculate_factorial(n - 1)

class DataProcessor:
    def __init__(self, data):
        self.data = data
    
    def process(self):
        return [x * 2 for x in self.data if x > 0]
'''
    
    # Use mock for testing
    analyzer = create_analyzer(use_mock=True)
    
    print("Testing LLM Analyzer...\n")
    
    for analysis_type in AnalysisType:
        print(f"=== {analysis_type.value.upper()} ===")
        result = analyzer.analyze_code(test_code, analysis_type)
        if result.success:
            print(result.content)
        else:
            print(f"Error: {result.error_message}")
        print()
