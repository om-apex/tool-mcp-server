"""Storage backend abstraction for Om Apex MCP Server.

Provides a unified interface for file I/O that works with both
local filesystem (Google Drive Desktop sync) and Google Drive API (remote).
"""

import json
import logging
import os
import platform
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

logger = logging.getLogger("om-apex-mcp")


class StorageBackend(ABC):
    """Abstract storage backend for reading/writing data files."""

    @abstractmethod
    def load_json(self, filename: str) -> dict:
        """Load a JSON file from the mcp-data directory."""
        ...

    @abstractmethod
    def save_json(self, filename: str, data: dict) -> None:
        """Save data to a JSON file in the mcp-data directory."""
        ...

    @abstractmethod
    def read_text(self, path: str) -> Optional[str]:
        """Read a text file by relative path from shared drive root. Returns None if not found."""
        ...

    @abstractmethod
    def write_text(self, path: str, content: str) -> None:
        """Write a text file by relative path from shared drive root."""
        ...

    @abstractmethod
    def append_text(self, path: str, content: str) -> None:
        """Append to a text file by relative path from shared drive root."""
        ...

    @abstractmethod
    def list_files(self, directory: str, pattern: str = "*.md") -> list[str]:
        """List files in a directory matching a glob pattern. Returns relative paths."""
        ...

    @abstractmethod
    def file_exists(self, path: str) -> bool:
        """Check if a file exists at the given relative path from shared drive root."""
        ...


class LocalStorage(StorageBackend):
    """Local filesystem storage — reads/writes via Google Drive Desktop sync."""

    def __init__(self, data_dir: Optional[Path] = None, shared_drive_root: Optional[Path] = None):
        if data_dir is None:
            data_dir = self._get_default_data_dir()
        self.data_dir = Path(data_dir).expanduser()
        self.shared_drive_root = shared_drive_root or self.data_dir.parent
        logger.info(f"LocalStorage: data_dir={self.data_dir}, shared_drive_root={self.shared_drive_root}")

    @staticmethod
    def _get_default_data_dir() -> Path:
        if platform.system() == "Darwin":
            return Path.home() / "Library/CloudStorage/GoogleDrive-nishad@omapex.com/Shared drives/om-apex/mcp-data"
        elif platform.system() == "Windows":
            return Path("H:/Shared drives/om-apex/mcp-data")
        else:
            return Path(__file__).parent.parent.parent / "data" / "context"

    def load_json(self, filename: str) -> dict:
        filepath = self.data_dir / filename
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
        return {}

    def save_json(self, filename: str, data: dict) -> None:
        filepath = self.data_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def read_text(self, path: str) -> Optional[str]:
        filepath = self.shared_drive_root / path
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        return None

    def write_text(self, path: str, content: str) -> None:
        filepath = self.shared_drive_root / path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

    def append_text(self, path: str, content: str) -> None:
        filepath = self.shared_drive_root / path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content)

    def list_files(self, directory: str, pattern: str = "*.md") -> list[str]:
        dir_path = self.shared_drive_root / directory
        if not dir_path.exists():
            return []
        return sorted(
            [str(f.relative_to(self.shared_drive_root)) for f in dir_path.glob(pattern)],
            reverse=True,
        )

    def file_exists(self, path: str) -> bool:
        return (self.shared_drive_root / path).exists()


class GoogleDriveStorage(StorageBackend):
    """Google Drive API storage for remote access via service account."""

    def __init__(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        if not creds_path:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE environment variable is required")

        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        self.service = build("drive", "v3", credentials=creds)

        # Shared Drive ID — set via env var or auto-discover
        self.shared_drive_id = os.environ.get("GOOGLE_SHARED_DRIVE_ID", "")
        if not self.shared_drive_id:
            self.shared_drive_id = self._find_shared_drive("om-apex")

        # Cache: relative path -> Drive file ID
        self._file_id_cache: dict[str, str] = {}
        # Cache: folder relative path -> Drive folder ID
        self._folder_id_cache: dict[str, str] = {}

        logger.info(f"GoogleDriveStorage: shared_drive_id={self.shared_drive_id}")

    def _find_shared_drive(self, name: str) -> str:
        """Find a shared drive by name."""
        response = self.service.drives().list(
            q=f"name = '{name}'",
            fields="drives(id, name)",
        ).execute()
        drives = response.get("drives", [])
        if not drives:
            raise ValueError(f"Shared Drive '{name}' not found")
        return drives[0]["id"]

    def _resolve_folder_id(self, folder_path: str) -> str:
        """Resolve a folder path to a Drive folder ID, walking the path."""
        if not folder_path or folder_path == ".":
            return self.shared_drive_id

        if folder_path in self._folder_id_cache:
            return self._folder_id_cache[folder_path]

        parts = folder_path.strip("/").split("/")
        parent_id = self.shared_drive_id

        for part in parts:
            current_path = "/".join(parts[:parts.index(part) + 1])
            if current_path in self._folder_id_cache:
                parent_id = self._folder_id_cache[current_path]
                continue

            response = self.service.files().list(
                q=f"name = '{part}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
                spaces="drive",
                fields="files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="drive",
                driveId=self.shared_drive_id,
            ).execute()
            files = response.get("files", [])
            if not files:
                raise FileNotFoundError(f"Folder not found: {folder_path} (missing: {part})")
            parent_id = files[0]["id"]
            self._folder_id_cache[current_path] = parent_id

        return parent_id

    def _resolve_file_id(self, path: str) -> Optional[str]:
        """Resolve a relative file path to a Drive file ID."""
        if path in self._file_id_cache:
            return self._file_id_cache[path]

        parts = path.strip("/").rsplit("/", 1)
        if len(parts) == 2:
            folder_path, filename = parts
        else:
            folder_path, filename = "", parts[0]

        try:
            parent_id = self._resolve_folder_id(folder_path)
        except FileNotFoundError:
            return None

        response = self.service.files().list(
            q=f"name = '{filename}' and '{parent_id}' in parents and trashed = false",
            spaces="drive",
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive",
            driveId=self.shared_drive_id,
        ).execute()
        files = response.get("files", [])
        if not files:
            return None

        file_id = files[0]["id"]
        self._file_id_cache[path] = file_id
        return file_id

    def _download_content(self, file_id: str) -> str:
        """Download file content by ID."""
        from googleapiclient.http import MediaIoBaseDownload
        import io

        request = self.service.files().get_media(
            fileId=file_id,
            supportsAllDrives=True,
        )
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue().decode("utf-8")

    def _upload_content(self, path: str, content: str, mime_type: str = "application/json") -> str:
        """Upload or update file content. Returns file ID."""
        from googleapiclient.http import MediaInMemoryUpload

        file_id = self._resolve_file_id(path)
        media = MediaInMemoryUpload(content.encode("utf-8"), mimetype=mime_type)

        if file_id:
            # Update existing file
            self.service.files().update(
                fileId=file_id,
                media_body=media,
                supportsAllDrives=True,
            ).execute()
            return file_id
        else:
            # Create new file
            parts = path.strip("/").rsplit("/", 1)
            if len(parts) == 2:
                folder_path, filename = parts
            else:
                folder_path, filename = "", parts[0]

            parent_id = self._resolve_folder_id(folder_path)
            file_metadata = {
                "name": filename,
                "parents": [parent_id],
            }
            result = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            new_id = result["id"]
            self._file_id_cache[path] = new_id
            return new_id

    def load_json(self, filename: str) -> dict:
        path = f"mcp-data/{filename}"
        file_id = self._resolve_file_id(path)
        if not file_id:
            return {}
        content = self._download_content(file_id)
        return json.loads(content)

    def save_json(self, filename: str, data: dict) -> None:
        path = f"mcp-data/{filename}"
        content = json.dumps(data, indent=2)
        self._upload_content(path, content, mime_type="application/json")

    def read_text(self, path: str) -> Optional[str]:
        file_id = self._resolve_file_id(path)
        if not file_id:
            return None
        return self._download_content(file_id)

    def write_text(self, path: str, content: str) -> None:
        self._upload_content(path, content, mime_type="text/plain")

    def append_text(self, path: str, content: str) -> None:
        existing = self.read_text(path)
        if existing:
            content = existing + content
        self._upload_content(path, content, mime_type="text/plain")

    def list_files(self, directory: str, pattern: str = "*.md") -> list[str]:
        try:
            folder_id = self._resolve_folder_id(directory)
        except FileNotFoundError:
            return []

        # Convert glob pattern to a simple suffix match
        # Supports "*.md" style patterns
        suffix = ""
        if pattern.startswith("*"):
            suffix = pattern[1:]

        results = []
        page_token = None
        while True:
            q = f"'{folder_id}' in parents and trashed = false"
            if suffix:
                q += f" and name contains '{suffix}'"

            response = self.service.files().list(
                q=q,
                spaces="drive",
                fields="nextPageToken, files(id, name)",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="drive",
                driveId=self.shared_drive_id,
                pageToken=page_token,
            ).execute()

            for f in response.get("files", []):
                rel_path = f"{directory}/{f['name']}"
                self._file_id_cache[rel_path] = f["id"]
                if not suffix or f["name"].endswith(suffix):
                    results.append(rel_path)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return sorted(results, reverse=True)

    def file_exists(self, path: str) -> bool:
        return self._resolve_file_id(path) is not None
