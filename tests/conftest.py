"""
Pytest configuration for Duro MCP tests.

Ensures the parent directory is in the path for imports.
"""

import sys
from pathlib import Path

# Add parent directory and src to path for imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))
sys.path.insert(0, str(parent_dir / "src"))
