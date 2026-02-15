"""
Mock MCP Harness - Test skills without real MCP connection.

This provides a fake `tools` object that:
- Implements read_file, glob_files, grep
- Returns fixtures from tests/fixtures/
- Tracks all calls for assertions

Usage in tests:
    from tests.mock_mcp import MockMCP

    mcp = MockMCP()
    mcp.add_fixture("src/app.tsx", "export default function App() {}")

    # Run your skill
    result = my_skill(tools=mcp, file_path="src/app.tsx")

    # Assert on calls
    assert mcp.was_called("read_file", "src/app.tsx")
"""

import fnmatch
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class MCPCall:
    """Record of a single MCP tool call."""
    method: str
    args: Dict[str, Any]
    result: Any


class MockMCP:
    """
    Mock MCP tools for testing skills.

    Provides fake implementations of common MCP operations
    that return controlled fixtures instead of hitting real files.
    """

    def __init__(self, fixtures_dir: Optional[Path] = None):
        self.fixtures_dir = fixtures_dir or Path(__file__).parent / "fixtures"
        self.calls: List[MCPCall] = []
        self.fixtures: Dict[str, str] = {}  # path -> content
        self.error_paths: Dict[str, str] = {}  # path -> error message

        # Load fixtures from directory
        self._load_fixtures()

    def _load_fixtures(self):
        """Load all fixtures from fixtures directory."""
        if self.fixtures_dir.exists():
            for fixture_file in self.fixtures_dir.rglob("*"):
                if fixture_file.is_file():
                    rel_path = str(fixture_file.relative_to(self.fixtures_dir))
                    # Normalize path separators
                    rel_path = rel_path.replace("\\", "/")
                    self.fixtures[rel_path] = fixture_file.read_text(encoding='utf-8')

    def add_fixture(self, path: str, content: str):
        """Add or update a fixture."""
        self.fixtures[path.replace("\\", "/")] = content

    def add_error(self, path: str, error: str):
        """Make a path return an error when read."""
        self.error_paths[path.replace("\\", "/")] = error

    def clear_calls(self):
        """Clear call history."""
        self.calls = []

    def was_called(self, method: str, *args_contain) -> bool:
        """Check if a method was called with args containing all given values."""
        for call in self.calls:
            if call.method != method:
                continue
            # Check if all args_contain items are in the call args
            arg_values = str(call.args)
            if all(str(a) in arg_values for a in args_contain):
                return True
        return False

    def call_count(self, method: str) -> int:
        """Count calls to a method."""
        return sum(1 for c in self.calls if c.method == method)

    def _record(self, method: str, args: Dict[str, Any], result: Any) -> Any:
        """Record a call and return result."""
        self.calls.append(MCPCall(method=method, args=args, result=result))
        return result

    # === MCP Tool Implementations ===

    def read_file(self, file_path: str) -> Dict[str, Any]:
        """
        Mock read_file - returns fixture content.

        Returns dict matching MCP response format:
        {"success": bool, "content": str, "error": str}
        """
        normalized = file_path.replace("\\", "/")

        # Check for configured errors
        if normalized in self.error_paths:
            return self._record("read_file", {"file_path": file_path}, {
                "success": False,
                "content": None,
                "error": self.error_paths[normalized]
            })

        # Check fixtures
        if normalized in self.fixtures:
            return self._record("read_file", {"file_path": file_path}, {
                "success": True,
                "content": self.fixtures[normalized],
                "error": None
            })

        # Try partial match (for tests that use just filename)
        for fixture_path, content in self.fixtures.items():
            if fixture_path.endswith(normalized) or normalized.endswith(fixture_path):
                return self._record("read_file", {"file_path": file_path}, {
                    "success": True,
                    "content": content,
                    "error": None
                })

        return self._record("read_file", {"file_path": file_path}, {
            "success": False,
            "content": None,
            "error": f"File not found in fixtures: {file_path}"
        })

    def glob_files(self, pattern: str, path: str = "") -> Dict[str, Any]:
        """
        Mock glob_files - matches fixtures against pattern.

        Returns dict: {"success": bool, "files": List[str], "error": str}
        """
        matched = []

        for fixture_path in self.fixtures.keys():
            # Apply path filter first
            if path and not fixture_path.startswith(path.replace("\\", "/")):
                continue

            # Check pattern
            if fnmatch.fnmatch(fixture_path, pattern):
                matched.append(fixture_path)

        return self._record("glob_files", {"pattern": pattern, "path": path}, {
            "success": True,
            "files": sorted(matched),
            "error": None
        })

    def grep(
        self,
        pattern: str,
        path: str = "",
        file_pattern: str = "*"
    ) -> Dict[str, Any]:
        """
        Mock grep - search fixtures for pattern.

        Returns dict: {"success": bool, "matches": List[dict], "error": str}
        """
        matches = []

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return self._record("grep", {"pattern": pattern}, {
                "success": False,
                "matches": [],
                "error": f"Invalid regex: {e}"
            })

        for fixture_path, content in self.fixtures.items():
            # Apply path filter
            if path and not fixture_path.startswith(path.replace("\\", "/")):
                continue

            # Apply file pattern filter
            if not fnmatch.fnmatch(fixture_path.split("/")[-1], file_pattern):
                continue

            # Search content
            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                if regex.search(line):
                    matches.append({
                        "file": fixture_path,
                        "line": i,
                        "content": line,
                        "match": regex.search(line).group(0)
                    })

        return self._record("grep", {"pattern": pattern, "path": path}, {
            "success": True,
            "matches": matches,
            "error": None
        })

    def write_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """
        Mock write_file - stores content in fixtures.

        Returns dict: {"success": bool, "error": str}
        """
        normalized = file_path.replace("\\", "/")

        # Check for write errors
        if normalized in self.error_paths:
            return self._record("write_file", {"file_path": file_path}, {
                "success": False,
                "error": self.error_paths[normalized]
            })

        # Store in fixtures
        self.fixtures[normalized] = content

        return self._record("write_file", {"file_path": file_path, "content": f"[{len(content)} chars]"}, {
            "success": True,
            "error": None
        })

    def list_files(self, path: str = "") -> Dict[str, Any]:
        """
        Mock list_files - list fixtures under path.

        Returns dict: {"success": bool, "files": List[str], "error": str}
        """
        files = []
        normalized_path = path.replace("\\", "/") if path else ""

        for fixture_path in self.fixtures.keys():
            if not normalized_path or fixture_path.startswith(normalized_path):
                files.append(fixture_path)

        return self._record("list_files", {"path": path}, {
            "success": True,
            "files": sorted(files),
            "error": None
        })


# === Test Fixture Builder ===

class FixtureBuilder:
    """
    Fluent builder for creating test fixtures.

    Usage:
        fixtures = (FixtureBuilder()
            .add_tsx("src/App.tsx", '''
                export default function App() {
                    return <div>Hello</div>
                }
            ''')
            .add_css("src/styles.css", '''
                .container { color: red; }
            ''')
            .build())

        mcp = MockMCP()
        for path, content in fixtures.items():
            mcp.add_fixture(path, content)
    """

    def __init__(self):
        self._fixtures: Dict[str, str] = {}

    def add_file(self, path: str, content: str) -> "FixtureBuilder":
        """Add a generic file."""
        self._fixtures[path] = content.strip()
        return self

    def add_tsx(self, path: str, content: str) -> "FixtureBuilder":
        """Add a TSX file."""
        return self.add_file(path, content)

    def add_css(self, path: str, content: str) -> "FixtureBuilder":
        """Add a CSS file."""
        return self.add_file(path, content)

    def add_json(self, path: str, content: str) -> "FixtureBuilder":
        """Add a JSON file."""
        return self.add_file(path, content)

    def add_pen(self, path: str, content: str) -> "FixtureBuilder":
        """Add a .pen design file."""
        return self.add_file(path, content)

    def build(self) -> Dict[str, str]:
        """Return all fixtures."""
        return self._fixtures.copy()


# === Pre-built Test Scenarios ===

def create_react_app_fixture() -> MockMCP:
    """Create a mock MCP with a basic React app structure."""
    mcp = MockMCP()

    mcp.add_fixture("src/App.tsx", '''
import React from 'react';
import './App.css';

export default function App() {
    return (
        <div className="container">
            <h1>Hello World</h1>
        </div>
    );
}
''')

    mcp.add_fixture("src/App.css", '''
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

h1 {
    color: #8B5CF6;
    font-size: 2rem;
}
''')

    mcp.add_fixture("src/index.tsx", '''
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
''')

    mcp.add_fixture("package.json", '''
{
    "name": "test-app",
    "version": "1.0.0",
    "dependencies": {
        "react": "^18.2.0",
        "react-dom": "^18.2.0"
    }
}
''')

    return mcp


def create_tailwind_fixture() -> MockMCP:
    """Create a mock MCP with Tailwind-styled components."""
    mcp = MockMCP()

    mcp.add_fixture("src/components/Button.tsx", '''
export function Button({ children, variant = "primary" }) {
    const classes = variant === "primary"
        ? "bg-purple-600 hover:bg-purple-700 text-white"
        : "bg-gray-200 hover:bg-gray-300 text-gray-800";

    return (
        <button className={`px-4 py-2 rounded-lg font-medium ${classes}`}>
            {children}
        </button>
    );
}
''')

    mcp.add_fixture("src/components/Card.tsx", '''
export function Card({ title, children }) {
    return (
        <div className="bg-white rounded-2xl shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-900 mb-4">{title}</h2>
            {children}
        </div>
    );
}
''')

    mcp.add_fixture("tailwind.config.js", '''
module.exports = {
    content: ["./src/**/*.{js,ts,jsx,tsx}"],
    theme: {
        extend: {
            colors: {
                purple: {
                    600: "#8B5CF6",
                    700: "#7C3AED"
                }
            }
        }
    }
}
''')

    return mcp


# CLI for testing the mock
if __name__ == "__main__":
    print("Testing MockMCP...")

    mcp = create_react_app_fixture()

    # Test read_file
    result = mcp.read_file("src/App.tsx")
    print(f"\nread_file('src/App.tsx'):")
    print(f"  success: {result['success']}")
    print(f"  content preview: {result['content'][:50]}...")

    # Test glob_files
    result = mcp.glob_files("*.tsx", "src")
    print(f"\nglob_files('*.tsx', 'src'):")
    print(f"  files: {result['files']}")

    # Test grep
    result = mcp.grep(r"export\s+default", path="src")
    print(f"\ngrep('export default', path='src'):")
    print(f"  matches: {len(result['matches'])}")
    for m in result['matches']:
        print(f"    - {m['file']}:{m['line']}")

    # Test call tracking
    print(f"\nTotal calls: {len(mcp.calls)}")
    print(f"read_file calls: {mcp.call_count('read_file')}")
    print(f"was_called('read_file', 'App.tsx'): {mcp.was_called('read_file', 'App.tsx')}")
