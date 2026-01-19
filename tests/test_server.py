"""
Tests for Om Apex MCP Server
"""

import json
import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from om_apex_mcp.server import load_json, save_json, DATA_DIR


class TestDataLoading:
    """Test JSON data loading functionality."""

    def test_load_company_structure(self):
        """Test loading company structure."""
        data = load_json("company_structure.json")
        assert data.get("holding_company", {}).get("name") == "Om Apex Holdings LLC"
        assert len(data.get("subsidiaries", [])) == 2

    def test_load_technology_decisions(self):
        """Test loading technology decisions."""
        data = load_json("technology_decisions.json")
        assert "decisions" in data
        assert len(data["decisions"]) > 0

    def test_load_domain_inventory(self):
        """Test loading domain inventory."""
        data = load_json("domain_inventory.json")
        assert data.get("summary", {}).get("total_domains") == 20

    def test_load_pending_tasks(self):
        """Test loading pending tasks."""
        data = load_json("pending_tasks.json")
        assert "tasks" in data
        assert len(data["tasks"]) > 0


class TestCompanyContext:
    """Test company context data."""

    def test_subsidiaries(self):
        """Test that subsidiaries are properly defined."""
        data = load_json("company_structure.json")
        subsidiaries = data.get("subsidiaries", [])
        names = [s.get("name") for s in subsidiaries]
        assert "Om Luxe Properties LLC" in names
        assert "Om AI Solutions LLC" in names

    def test_ownership(self):
        """Test ownership structure."""
        data = load_json("company_structure.json")
        ownership = data.get("holding_company", {}).get("ownership", {})
        assert "nishad_tambe" in ownership
        assert "sumedha_tambe" in ownership


class TestTasks:
    """Test task data structure."""

    def test_task_structure(self):
        """Test that tasks have required fields."""
        data = load_json("pending_tasks.json")
        for task in data.get("tasks", []):
            assert "id" in task
            assert "description" in task
            assert "status" in task


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
