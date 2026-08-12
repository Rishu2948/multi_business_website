"""
CI/unit guard to prevent forbidden local session-lookup patterns in route files.

This test ensures that route files use the centralized Auth_Module for authentication
and do not contain local session-lookup helpers that bypass the standard auth flow.

Forbidden patterns:
- Local `get_optional_user` or `get_user` functions
- Direct `user_sessions.find_one` queries
- Direct `session_token` cookie extraction without Auth_Module
- Bearer header parsing without Auth_Module validation
"""

import pytest
import sys
from pathlib import Path
import re

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


class TestForbiddenAuthPatterns:
    """Test for forbidden local auth patterns in route files."""
    
    # Forbidden patterns that indicate local auth implementations
    FORBIDDEN_PATTERNS = [
        r'async def get_optional_user\(request: Request\):',
        r'async def get_user\(request: Request\):',
        r'async def _get_user_from_request\(request: Request\):',
        r'await db\.user_sessions\.find_one\(\{"session_token":',
        r'request\.cookies\.get\("session_token"\)\s*or\s*request\.headers\.get\("authorization',
        r'request\.headers\.get\("authorization"\)\.replace\("Bearer ',
        r'session_token\s*=\s*request\.cookies\.get\("session_token"\)',
    ]
    
    # Files that should be checked (route files)
    ROUTE_FILES = [
        "order_routes.py",
        "custom_order_routes.py", 
        "ecommerce_routes.py",
        "additional_routes.py",
        "category_routes.py",
        "store_routes.py",
        "offers_routes.py",
        "collections_routes.py",
        "announcements_routes.py",
        "business_config_routes.py",
        "location_routes.py",
        "order_management_routes.py",
    ]
    
    # Allowed files that can contain these patterns (Auth_Module itself, tests, etc.)
    ALLOWED_FILES = [
        "server.py",  # Main server file can have legacy implementations during migration
        "auth/",       # Auth_Module files themselves
        "tests/",      # Test files
    ]
    
    @pytest.fixture
    def backend_dir(self):
        """Get backend directory path."""
        return backend_path
    
    def test_no_forbidden_patterns_in_routes(self, backend_dir):
        """Test that route files don't contain forbidden auth patterns."""
        violations = []
        
        for route_file in self.ROUTE_FILES:
            file_path = backend_dir / route_file
            if not file_path.exists():
                continue
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Check each forbidden pattern
            for pattern in self.FORBIDDEN_PATTERNS:
                if re.search(pattern, content):
                    violations.append({
                        'file': route_file,
                        'pattern': pattern,
                        'line': self._find_pattern_line(content, pattern)
                    })
        
        if violations:
            violation_details = "\n".join([
                f"  - {v['file']}:{v['line']} - Pattern: {v['pattern']}"
                for v in violations
            ])
            pytest.fail(
                f"Found forbidden local auth patterns in route files:\n{violation_details}\n"
                f"These files should use the centralized Auth_Module (backend/auth/) "
                f"instead of implementing local auth helpers."
            )
    
    def _find_pattern_line(self, content, pattern):
        """Find the line number where a pattern first appears."""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line):
                return i
        return 0
    
    def test_auth_module_exports_required_dependencies(self, backend_dir):
        """Test that Auth_Module exports the required dependencies."""
        auth_init_path = backend_dir / "auth" / "__init__.py"
        
        if not auth_init_path.exists():
            pytest.fail("Auth_Module __init__.py not found")
        
        with open(auth_init_path, 'r') as f:
            content = f.read()
        
        # Required exports
        required_exports = [
            'get_current_user',
            'get_optional_user', 
            'require_roles',
            'require_business_access',
            'check_business_access',
        ]
        
        missing_exports = []
        for export in required_exports:
            if export not in content:
                missing_exports.append(export)
        
        if missing_exports:
            pytest.fail(
                f"Auth_Module __init__.py is missing required exports: {missing_exports}"
            )
    
    def test_no_direct_user_sessions_queries_in_routes(self, backend_dir):
        """Test that route files don't directly query user_sessions collection."""
        violations = []
        
        for route_file in self.ROUTE_FILES:
            file_path = backend_dir / route_file
            if not file_path.exists():
                continue
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Check for direct user_sessions queries
            if re.search(r'db\.user_sessions\.find_one', content):
                violations.append({
                    'file': route_file,
                    'pattern': 'db.user_sessions.find_one',
                    'line': self._find_pattern_line(content, r'db\.user_sessions\.find_one')
                })
            
            if re.search(r'db\.user_sessions\.find\(', content):
                violations.append({
                    'file': route_file,
                    'pattern': 'db.user_sessions.find(',
                    'line': self._find_pattern_line(content, r'db\.user_sessions\.find\(')
                })
        
        if violations:
            violation_details = "\n".join([
                f"  - {v['file']}:{v['line']} - Pattern: {v['pattern']}"
                for v in violations
            ])
            pytest.fail(
                f"Found direct user_sessions queries in route files:\n{violation_details}\n"
                f"Route files should use Auth_Module dependencies (get_current_user, get_optional_user) "
                f"instead of directly querying user_sessions."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
