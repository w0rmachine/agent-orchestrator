"""Tests for vault watcher module."""
import tempfile
from pathlib import Path

import pytest

from backend.sync.vault_watcher import VaultWatcher, compute_file_hash


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_hash_existing_file(self):
        """Test computing hash of an existing file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            f.write("Hello, World!")
            filepath = f.name

        try:
            hash_value = compute_file_hash(filepath)

            # SHA256 hash should be 64 hex characters
            assert len(hash_value) == 64
            assert all(c in "0123456789abcdef" for c in hash_value)
        finally:
            Path(filepath).unlink()

    def test_hash_is_consistent(self):
        """Test that same content produces same hash."""
        content = "Test content for hashing"

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            f.write(content)
            filepath = f.name

        try:
            hash1 = compute_file_hash(filepath)
            hash2 = compute_file_hash(filepath)

            assert hash1 == hash2
        finally:
            Path(filepath).unlink()

    def test_different_content_different_hash(self):
        """Test that different content produces different hashes."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f1:
            f1.write("Content A")
            filepath1 = f1.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f2:
            f2.write("Content B")
            filepath2 = f2.name

        try:
            hash1 = compute_file_hash(filepath1)
            hash2 = compute_file_hash(filepath2)

            assert hash1 != hash2
        finally:
            Path(filepath1).unlink()
            Path(filepath2).unlink()

    def test_hash_nonexistent_file(self):
        """Test computing hash of nonexistent file returns empty string."""
        hash_value = compute_file_hash("/nonexistent/file.md")

        assert hash_value == ""

    def test_hash_empty_file(self):
        """Test computing hash of empty file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            # Write nothing
            filepath = f.name

        try:
            hash_value = compute_file_hash(filepath)

            # Should still produce a valid hash
            assert len(hash_value) == 64
        finally:
            Path(filepath).unlink()


class TestVaultWatcher:
    """Tests for VaultWatcher class."""

    def test_init_with_existing_file(self):
        """Test initializing watcher with existing file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".md") as f:
            f.write("Initial content")
            filepath = f.name

        try:
            async def on_change(hash_val):
                pass

            watcher = VaultWatcher(filepath, on_change)

            assert watcher.filepath == Path(filepath).resolve()
            assert watcher.last_hash != ""
            assert watcher.observer is None  # Not started yet
        finally:
            Path(filepath).unlink()

    def test_init_with_nonexistent_file(self):
        """Test initializing watcher with nonexistent file."""
        async def on_change(hash_val):
            pass

        watcher = VaultWatcher("/tmp/nonexistent_test_file.md", on_change)

        assert watcher.last_hash == ""

    def test_start_requires_existing_directory(self):
        """Test that start raises error if directory doesn't exist."""
        async def on_change(hash_val):
            pass

        watcher = VaultWatcher("/nonexistent/directory/file.md", on_change)

        with pytest.raises(FileNotFoundError):
            watcher.start()

    def test_start_and_stop(self):
        """Test starting and stopping the watcher."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("Initial content")

            async def on_change(hash_val):
                pass

            watcher = VaultWatcher(str(filepath), on_change)

            # Start watching
            watcher.start()
            assert watcher.observer is not None

            # Stop watching
            watcher.stop()
            assert watcher.observer is None

    def test_start_is_idempotent(self):
        """Test that calling start multiple times is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("Initial content")

            async def on_change(hash_val):
                pass

            watcher = VaultWatcher(str(filepath), on_change)

            watcher.start()
            observer1 = watcher.observer

            watcher.start()  # Should be no-op
            assert watcher.observer is observer1

            watcher.stop()

    def test_stop_is_idempotent(self):
        """Test that calling stop multiple times is safe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("Initial content")

            async def on_change(hash_val):
                pass

            watcher = VaultWatcher(str(filepath), on_change)

            watcher.start()
            watcher.stop()
            watcher.stop()  # Should be safe

            assert watcher.observer is None

    def test_custom_debounce(self):
        """Test custom debounce setting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.md"
            filepath.write_text("Initial content")

            async def on_change(hash_val):
                pass

            watcher = VaultWatcher(str(filepath), on_change, debounce_ms=1000)

            assert watcher.debounce_ms == 1000
