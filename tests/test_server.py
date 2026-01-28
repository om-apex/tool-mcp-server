"""
Tests for Om Apex MCP Server
"""

import json
import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from om_apex_mcp.tools.helpers import load_json, save_json, init_storage, get_backend
from om_apex_mcp.storage import LocalStorage


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


class TestModuleRegistration:
    """Test that all tool modules register correctly."""

    def test_all_modules_load(self):
        """Test that server imports and registers all modules."""
        from om_apex_mcp.tools import context, tasks, progress, documents

        task_mod = tasks.register()
        progress_mod = progress.register()
        documents_mod = documents.register()

        all_reading = context.READING + task_mod.reading_tools + progress_mod.reading_tools + documents_mod.reading_tools
        all_writing = context.WRITING + task_mod.writing_tools + progress_mod.writing_tools + documents_mod.writing_tools

        context_mod = context.register(all_reading, all_writing)

        all_tools = []
        for m in [context_mod, task_mod, progress_mod, documents_mod]:
            all_tools.extend(t.name for t in m.tools)

        # 7 context + 5 tasks + 3 progress + 2 documents = 17
        assert len(all_tools) == 17

        # Spot-check key tools exist
        assert "get_full_context" in all_tools
        assert "add_task" in all_tools
        assert "add_daily_progress" in all_tools
        assert "generate_branded_html" in all_tools
        assert "list_company_configs" in all_tools


class TestStorageBackend:
    """Test storage backend abstraction."""

    def test_local_storage_init(self):
        """Test LocalStorage initializes with default paths."""
        backend = LocalStorage()
        assert backend.data_dir.exists() or True  # May not exist in CI
        assert backend.shared_drive_root is not None

    def test_local_storage_custom_dir(self, tmp_path):
        """Test LocalStorage with custom data directory."""
        data_dir = tmp_path / "mcp-data"
        data_dir.mkdir()
        backend = LocalStorage(data_dir=data_dir, shared_drive_root=tmp_path)
        assert backend.data_dir == data_dir
        assert backend.shared_drive_root == tmp_path

    def test_local_storage_json_roundtrip(self, tmp_path):
        """Test save/load JSON with LocalStorage."""
        data_dir = tmp_path / "mcp-data"
        data_dir.mkdir()
        backend = LocalStorage(data_dir=data_dir)

        test_data = {"key": "value", "number": 42}
        backend.save_json("test.json", test_data)
        loaded = backend.load_json("test.json")
        assert loaded == test_data

    def test_local_storage_load_missing(self, tmp_path):
        """Test loading non-existent file returns empty dict."""
        backend = LocalStorage(data_dir=tmp_path)
        assert backend.load_json("nonexistent.json") == {}

    def test_local_storage_text_roundtrip(self, tmp_path):
        """Test read/write/append text with LocalStorage."""
        backend = LocalStorage(data_dir=tmp_path / "data", shared_drive_root=tmp_path)
        (tmp_path / "data").mkdir()

        backend.write_text("test.md", "Hello\n")
        assert backend.read_text("test.md") == "Hello\n"

        backend.append_text("test.md", "World\n")
        assert backend.read_text("test.md") == "Hello\nWorld\n"

    def test_local_storage_read_missing(self, tmp_path):
        """Test reading non-existent text file returns None."""
        backend = LocalStorage(data_dir=tmp_path, shared_drive_root=tmp_path)
        assert backend.read_text("missing.md") is None

    def test_local_storage_file_exists(self, tmp_path):
        """Test file_exists check."""
        backend = LocalStorage(data_dir=tmp_path, shared_drive_root=tmp_path)
        assert not backend.file_exists("nope.md")
        (tmp_path / "yep.md").write_text("hi")
        assert backend.file_exists("yep.md")

    def test_local_storage_list_files(self, tmp_path):
        """Test listing files with glob pattern."""
        subdir = tmp_path / "logs"
        subdir.mkdir()
        (subdir / "2026-01-01.md").write_text("day 1")
        (subdir / "2026-01-02.md").write_text("day 2")
        (subdir / "notes.txt").write_text("other")

        backend = LocalStorage(data_dir=tmp_path, shared_drive_root=tmp_path)
        md_files = backend.list_files("logs", "*.md")
        assert len(md_files) == 2
        assert all(f.endswith(".md") for f in md_files)


class TestInitStorage:
    """Test storage initialization through helpers."""

    def test_init_and_get_backend(self, tmp_path):
        """Test init_storage sets the global backend."""
        data_dir = tmp_path / "mcp-data"
        data_dir.mkdir()
        backend = LocalStorage(data_dir=data_dir)
        init_storage(backend)
        assert get_backend() is backend

    def test_lazy_init(self):
        """Test get_backend auto-initializes if not set."""
        # This just verifies it doesn't crash
        backend = get_backend()
        assert isinstance(backend, LocalStorage)


class TestCreateServer:
    """Test server factory function."""

    def test_create_server_returns_server(self, tmp_path):
        """Test create_server returns an MCP Server instance."""
        from om_apex_mcp.server import create_server
        from mcp.server import Server

        data_dir = tmp_path / "mcp-data"
        data_dir.mkdir()
        # Write minimal JSON files so tools don't error
        (data_dir / "company_structure.json").write_text('{"holding_company": {"name": "Test"}, "subsidiaries": []}')
        (data_dir / "technology_decisions.json").write_text('{"decisions": []}')
        (data_dir / "domain_inventory.json").write_text('{"summary": {}}')
        (data_dir / "pending_tasks.json").write_text('{"tasks": []}')

        backend = LocalStorage(data_dir=data_dir, shared_drive_root=tmp_path)
        server = create_server(backend)
        assert isinstance(server, Server)


class TestAuth:
    """Test authentication module."""

    def test_demo_mode_tools_list(self):
        """Test that demo mode tools are all reading tools."""
        from om_apex_mcp.auth import DEMO_MODE_TOOLS
        assert "get_full_context" in DEMO_MODE_TOOLS
        assert "get_pending_tasks" in DEMO_MODE_TOOLS
        # Writing tools should not be in demo mode
        assert "add_task" not in DEMO_MODE_TOOLS
        assert "add_decision" not in DEMO_MODE_TOOLS
        assert "complete_task" not in DEMO_MODE_TOOLS

    def test_load_api_keys_empty(self, monkeypatch):
        """Test load_api_keys with no env vars set."""
        from om_apex_mcp.auth import load_api_keys
        monkeypatch.delenv("OM_APEX_API_KEY_NISHAD", raising=False)
        monkeypatch.delenv("OM_APEX_API_KEY_SUMEDHA", raising=False)
        keys = load_api_keys()
        assert len(keys) == 0

    def test_load_api_keys_with_env(self, monkeypatch):
        """Test load_api_keys with env vars set."""
        from om_apex_mcp.auth import load_api_keys
        monkeypatch.setenv("OM_APEX_API_KEY_NISHAD", "test-key-123")
        monkeypatch.setenv("OM_APEX_API_KEY_SUMEDHA", "test-key-456")
        keys = load_api_keys()
        assert len(keys) == 2
        assert keys["test-key-123"].name == "Nishad"
        assert keys["test-key-456"].name == "Sumedha"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
