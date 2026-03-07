"""
Outlook COM inbox polling for status engine (Phase 3).

Requires: pywin32 (pip install pywin32). Outlook desktop must be running.
Resolves folder from config (default Inbox or shared store + optional folder path),
returns oldest unread age in minutes and unread count.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

try:
    import win32com.client
    from pywintypes import com_error
    _OUTLOOK_AVAILABLE = True
except ImportError:
    _OUTLOOK_AVAILABLE = False
    com_error = Exception  # type: ignore[misc, assignment]

# Outlook folder type constant (OlDefaultFolders)
OL_FOLDER_INBOX = 6

log = logging.getLogger(__name__)


@dataclass
class InboxResult:
    """Result of polling a folder for unread age."""
    oldest_unread_minutes: float | None  # None if no unread
    unread_count: int
    folder_name: str


def _get_outlook_folder(
    folder_source: str,
    store_display_name: str | None,
    folder_path: str | None,
) -> Any:
    """
    Resolve the Outlook folder to poll.
    Returns COM folder object; raises on error or not found.
    """
    outlook = win32com.client.Dispatch("Outlook.Application")
    namespace = outlook.GetNamespace("MAPI")

    if folder_source == "default_inbox" or not store_display_name:
        inbox = namespace.GetDefaultFolder(OL_FOLDER_INBOX)
        folder = inbox
        if folder_path:
            for part in (folder_path or "").replace("/", "\\").split("\\"):
                part = part.strip()
                if not part:
                    continue
                try:
                    folder = folder.Folders(part)
                except Exception as e:
                    raise LookupError(f"Subfolder '{part}' not found under Inbox: {e}") from e
        return folder

    # Shared store: find by display name
    for i in range(1, namespace.Folders.Count + 1):
        store = namespace.Folders(i)
        if getattr(store, "DisplayName", None) == store_display_name:
            inbox = store.GetDefaultFolder(OL_FOLDER_INBOX)
            folder = inbox
            if folder_path:
                for part in (folder_path or "").replace("/", "\\").split("\\"):
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        folder = folder.Folders(part)
                    except Exception as e:
                        raise LookupError(f"Subfolder '{part}' not found: {e}") from e
            return folder

    raise LookupError(f"Store not found: '{store_display_name}'")


def get_oldest_unread_minutes(config: dict) -> InboxResult:
    """
    Open Outlook folder from config, return oldest unread age (minutes) and count.
    Config keys: outlook.folderSource, outlook.storeDisplayName, outlook.folderPath.
    Raises on COM error or missing folder; returns InboxResult with oldest_unread_minutes=None if no unread.
    """
    if not _OUTLOOK_AVAILABLE:
        raise RuntimeError("pywin32 not installed; pip install pywin32")

    outlook_cfg = config.get("outlook") or {}
    folder_source = (outlook_cfg.get("folderSource") or "default_inbox").strip().lower()
    store_name = outlook_cfg.get("storeDisplayName") or ""
    if isinstance(store_name, str):
        store_name = store_name.strip() or None
    folder_path = outlook_cfg.get("folderPath") or None
    if isinstance(folder_path, str):
        folder_path = folder_path.strip() or None

    folder = _get_outlook_folder(folder_source, store_name, folder_path)
    folder_display = getattr(folder, "Name", "Inbox")

    items = folder.Items
    now = datetime.now()
    oldest: datetime | None = None
    unread_count = 0

    # Iterate; Items can be filtered with Restrict but UnRead + ReceivedTime iteration is simple
    try:
        for i in range(1, items.Count + 1):
            try:
                item = items(i)
                if not getattr(item, "UnRead", False):
                    continue
                unread_count += 1
                rt = getattr(item, "ReceivedTime", None)
                if rt is not None:
                    if hasattr(rt, "timetuple"):
                        received = rt
                    else:
                        received = datetime.fromtimestamp(rt)
                    if oldest is None or received < oldest:
                        oldest = received
            except (com_error, AttributeError, TypeError):
                continue
    except com_error as e:
        log.warning("Outlook Items access error: %s", e)
        raise

    if oldest is None:
        return InboxResult(oldest_unread_minutes=None, unread_count=unread_count, folder_name=folder_display)

    delta = now - oldest
    oldest_minutes = max(0.0, delta.total_seconds() / 60.0)
    return InboxResult(
        oldest_unread_minutes=oldest_minutes,
        unread_count=unread_count,
        folder_name=folder_display,
    )
