"""File watcher for incremental vault synchronization."""

import asyncio
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from backend.config import settings
from .pipeline import ExtractionPipeline


class VaultEventHandler(FileSystemEventHandler):
    """Handle file system events for the vault."""

    SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".gif"}

    def __init__(
        self,
        pipeline: ExtractionPipeline,
        on_change: Optional[Callable[[str, str], None]] = None,
        debounce_seconds: float = 1.0,
    ):
        self.pipeline = pipeline
        self.on_change = on_change
        self.debounce_seconds = debounce_seconds
        self._pending_events: dict[str, asyncio.Task] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _is_supported_file(self, path: str) -> bool:
        """Check if the file type is supported."""
        return Path(path).suffix.lower() in self.SUPPORTED_EXTENSIONS

    def _should_ignore(self, path: str) -> bool:
        """Check if the path should be ignored."""
        p = Path(path)
        # Ignore hidden files and .obsidian folder
        return any(part.startswith(".") for part in p.parts)

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation."""
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if self._is_supported_file(event.src_path):
            self._schedule_processing(event.src_path, "created")

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification."""
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if self._is_supported_file(event.src_path):
            self._schedule_processing(event.src_path, "modified")

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion."""
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if self._is_supported_file(event.src_path):
            self._handle_deletion(event.src_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file moves/renames."""
        if event.is_directory:
            return

        src_supported = self._is_supported_file(event.src_path)
        dest_supported = self._is_supported_file(event.dest_path)

        if src_supported and not self._should_ignore(event.src_path):
            self._handle_deletion(event.src_path)

        if dest_supported and not self._should_ignore(event.dest_path):
            self._schedule_processing(event.dest_path, "moved")

    def _schedule_processing(self, path: str, event_type: str) -> None:
        """Schedule file processing with debouncing."""
        # Cancel any pending task for this file
        if path in self._pending_events:
            self._pending_events[path].cancel()

        # For now, process synchronously since we might not have an event loop
        try:
            self._process_file(path, event_type)
        except Exception as e:
            print(f"Error processing {path}: {e}")

    def _process_file(self, path: str, event_type: str) -> None:
        """Process a file change."""
        try:
            file_path = Path(path)
            if file_path.exists():
                content = self.pipeline.process_single_file(file_path)
                if content and self.on_change:
                    self.on_change(path, event_type)
                print(f"Processed {event_type}: {path}")
        except Exception as e:
            print(f"Error processing {path}: {e}")

    def _handle_deletion(self, path: str) -> None:
        """Handle file deletion by removing from graph and vector store."""
        try:
            file_path = Path(path)
            relative_path = str(file_path.relative_to(self.pipeline.vault_path))

            # Generate document ID (same logic as in models.py)
            import hashlib
            doc_id = hashlib.md5(relative_path.encode()).hexdigest()[:16]

            # Remove from vector store
            self.pipeline.vector_store.delete_document(doc_id)
            self.pipeline.vector_store.delete_document_chunks(doc_id)

            # Remove from graph would require a delete method
            # For now just log
            print(f"Deleted: {path}")

            if self.on_change:
                self.on_change(path, "deleted")

        except Exception as e:
            print(f"Error handling deletion of {path}: {e}")


class VaultWatcher:
    """Watch vault for changes and sync to knowledge graph."""

    def __init__(
        self,
        vault_path: Path = None,
        pipeline: ExtractionPipeline = None,
        on_change: Optional[Callable[[str, str], None]] = None,
    ):
        self.vault_path = vault_path or settings.vault_path
        self.pipeline = pipeline or ExtractionPipeline()
        self.on_change = on_change

        self._observer: Optional[Observer] = None
        self._running = False

    def start(self) -> None:
        """Start watching the vault."""
        if self._running:
            return

        # Initialize pipeline
        self.pipeline.initialize()

        # Create event handler
        handler = VaultEventHandler(
            pipeline=self.pipeline,
            on_change=self.on_change,
        )

        # Create and start observer
        self._observer = Observer()
        self._observer.schedule(
            handler,
            str(self.vault_path),
            recursive=True,
        )
        self._observer.start()
        self._running = True

        print(f"Started watching: {self.vault_path}")

    def stop(self) -> None:
        """Stop watching the vault."""
        if not self._running:
            return

        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None

        self.pipeline.close()
        self._running = False

        print("Stopped watching vault")

    @property
    def is_running(self) -> bool:
        """Check if watcher is running."""
        return self._running

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
