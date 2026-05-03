from pathlib import Path

import pytest

from app.storage import LocalImageStorage, StorageError


def test_saves_image_under_date_directory_with_safe_random_name(tmp_path: Path):
    storage = LocalImageStorage(root_dir=tmp_path, max_bytes=1024)

    saved = storage.save_upload(
        original_filename="用户传来的照片.jpg",
        content_type="image/jpeg",
        data=b"fake-image",
    )

    saved_path = tmp_path / saved.relative_path
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"fake-image"
    assert saved.relative_path.endswith(".jpg")
    assert "用户传来的照片" not in saved.relative_path
    assert len(Path(saved.relative_path).parts) == 4


def test_rejects_unsupported_image_type(tmp_path: Path):
    storage = LocalImageStorage(root_dir=tmp_path, max_bytes=1024)

    with pytest.raises(StorageError, match="unsupported"):
        storage.save_upload(
            original_filename="food.gif",
            content_type="image/gif",
            data=b"gif",
        )


def test_rejects_oversized_image(tmp_path: Path):
    storage = LocalImageStorage(root_dir=tmp_path, max_bytes=3)

    with pytest.raises(StorageError, match="too large"):
        storage.save_upload(
            original_filename="food.jpg",
            content_type="image/jpeg",
            data=b"1234",
        )
