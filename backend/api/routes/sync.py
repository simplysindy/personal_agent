"""Sync and extraction API routes."""

from typing import Optional
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from backend.config import settings
from backend.extraction.pipeline import ExtractionPipeline
from backend.extraction.watcher import VaultWatcher


router = APIRouter(prefix="/sync", tags=["sync"])

# Global instances
_pipeline: Optional[ExtractionPipeline] = None
_watcher: Optional[VaultWatcher] = None
_sync_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_file": "",
    "error": None,
}


def set_pipeline(pipeline: ExtractionPipeline) -> None:
    """Set the extraction pipeline instance."""
    global _pipeline
    _pipeline = pipeline


class SyncResponse(BaseModel):
    """Sync operation response."""

    status: str
    message: str
    stats: dict = {}


class SyncStatus(BaseModel):
    """Current sync status."""

    running: bool
    progress: int
    total: int
    current_file: str
    error: Optional[str] = None


class VaultStats(BaseModel):
    """Vault file statistics."""

    projects: int
    total_files: int
    by_type: dict


@router.get("/status", response_model=SyncStatus)
async def get_sync_status() -> SyncStatus:
    """Get current sync status."""
    return SyncStatus(**_sync_status)


@router.get("/vault/stats", response_model=VaultStats)
async def get_vault_stats() -> VaultStats:
    """Get vault file statistics."""
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    stats = _pipeline.scan_vault()

    return VaultStats(
        projects=stats.get("projects", 0),
        total_files=stats.get("total_files", 0),
        by_type={
            k: v for k, v in stats.items()
            if k not in ("projects", "total_files")
        },
    )


@router.post("/full", response_model=SyncResponse)
async def start_full_sync(background_tasks: BackgroundTasks) -> SyncResponse:
    """
    Start a full synchronization of the vault.

    This extracts all documents and builds the knowledge graph.
    Runs in the background.
    """
    global _sync_status

    if _sync_status["running"]:
        return SyncResponse(
            status="already_running",
            message="A sync is already in progress",
        )

    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    # Reset status
    _sync_status = {
        "running": True,
        "progress": 0,
        "total": 0,
        "current_file": "",
        "error": None,
    }

    # Run in background
    background_tasks.add_task(_run_full_sync)

    return SyncResponse(
        status="started",
        message="Full sync started in background",
    )


def _run_full_sync():
    """Run the full sync process.

    NOTE: This must be a regular (non-async) function so that Starlette's
    BackgroundTasks runs it in a thread pool instead of on the event loop.
    process_vault() is blocking and would freeze the entire server otherwise.
    """
    global _sync_status

    def progress_callback(current: int, total: int, file_path: str):
        _sync_status["progress"] = current
        _sync_status["total"] = total
        _sync_status["current_file"] = file_path

    try:
        stats = _pipeline.process_vault(
            parallel=True,
            max_workers=4,
            progress_callback=progress_callback,
        )

        _sync_status["running"] = False
        _sync_status["stats"] = stats

    except Exception as e:
        _sync_status["running"] = False
        _sync_status["error"] = str(e)


@router.post("/file", response_model=SyncResponse)
async def sync_single_file(file_path: str) -> SyncResponse:
    """Sync a single file from the vault."""
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    full_path = Path(settings.vault_path) / file_path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    try:
        content = _pipeline.process_single_file(full_path)

        if content:
            return SyncResponse(
                status="success",
                message=f"Synced: {file_path}",
                stats={
                    "concepts": len(content.concepts),
                    "people": len(content.people),
                    "images": len(content.images),
                },
            )
        else:
            return SyncResponse(
                status="skipped",
                message=f"Unsupported file type: {file_path}",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watcher/start", response_model=SyncResponse)
async def start_watcher() -> SyncResponse:
    """Start the file watcher for incremental sync."""
    global _watcher

    if _watcher and _watcher.is_running:
        return SyncResponse(
            status="already_running",
            message="Watcher is already running",
        )

    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        _watcher = VaultWatcher(
            vault_path=settings.vault_path,
            pipeline=_pipeline,
        )
        _watcher.start()

        return SyncResponse(
            status="started",
            message="File watcher started",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/watcher/stop", response_model=SyncResponse)
async def stop_watcher() -> SyncResponse:
    """Stop the file watcher."""
    global _watcher

    if not _watcher or not _watcher.is_running:
        return SyncResponse(
            status="not_running",
            message="Watcher is not running",
        )

    try:
        _watcher.stop()
        return SyncResponse(
            status="stopped",
            message="File watcher stopped",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/watcher/status")
async def get_watcher_status() -> dict:
    """Get watcher status."""
    return {
        "running": _watcher.is_running if _watcher else False,
        "vault_path": str(settings.vault_path),
    }
