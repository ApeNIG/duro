"""
Pytest fixtures for adversarial tests.
"""

import sys
import pytest
from pathlib import Path

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

# Add parent for harness import
sys.path.insert(0, str(Path(__file__).parent))

from harness import IsolatedTestDB, MockEmbedder, TestArtifact


@pytest.fixture
def isolated_db():
    """Provide an isolated test database that auto-cleans."""
    with IsolatedTestDB(name="pytest") as db:
        yield db


@pytest.fixture
def mock_embedder():
    """Provide a mock embedder for controlled tests."""
    return MockEmbedder(dimension=384)


@pytest.fixture
def sample_facts(isolated_db):
    """Create sample facts for testing."""
    facts = [
        TestArtifact(
            id="fact_test_001",
            type="fact",
            claim="Python uses indentation for code blocks",
            tags=["python", "syntax"]
        ),
        TestArtifact(
            id="fact_test_002",
            type="fact",
            claim="JavaScript uses curly braces for code blocks",
            tags=["javascript", "syntax"]
        ),
        TestArtifact(
            id="fact_test_003",
            type="fact",
            claim="SQL uses semicolons to terminate statements",
            tags=["sql", "syntax"]
        ),
    ]

    for fact in facts:
        isolated_db.add_artifact(fact)

    return facts
