from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


class StorageError(ValueError):
    pass


@dataclass(frozen=True)
class SavedImage:
    image_id: str
    relative_path: str
    content_type: str
    size_bytes: int


class LocalImageStorage:
    _extensions = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    def __init__(self, root_dir: str | Path, max_bytes: int) -> None:
        self.root_dir = Path(root_dir)
        self.max_bytes = max_bytes

    def save_upload(self, original_filename: str, content_type: str, data: bytes) -> SavedImage:
        if content_type not in self._extensions:
            raise StorageError(f"unsupported image type: {content_type}")
        if len(data) > self.max_bytes:
            raise StorageError(f"image too large: {len(data)} bytes")
        if not data:
            raise StorageError("image is empty")

        now = datetime.now(timezone.utc)
        image_id = f"img_{uuid4().hex}"
        relative_dir = Path(str(now.year)) / f"{now.month:02d}" / f"{now.day:02d}"
        filename = f"{image_id}{self._extensions[content_type]}"
        target_dir = self.root_dir / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        target_path.write_bytes(data)

        return SavedImage(
            image_id=image_id,
            relative_path=str(relative_dir / filename).replace("\\", "/"),
            content_type=content_type,
            size_bytes=len(data),
        )

    def absolute_path(self, relative_path: str) -> Path:
        resolved = (self.root_dir / relative_path).resolve()
        root = self.root_dir.resolve()
        if root not in resolved.parents and resolved != root:
            raise StorageError("invalid image path")
        return resolved

    def cleanup_expired(self, keep_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
        removed = 0
        if not self.root_dir.exists():
            return removed
        for path in self.root_dir.rglob("*"):
            if not path.is_file():
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            if modified < cutoff:
                path.unlink()
                removed += 1
        return removed
