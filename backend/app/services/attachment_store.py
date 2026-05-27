from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(slots=True)
class StoredImageAttachment:
    attachment_id: str
    content: bytes
    mime_type: str
    expires_at: datetime


class InMemoryAttachmentStore:
    def __init__(self, *, ttl_seconds: int = 30 * 60):
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, StoredImageAttachment] = {}
        self._lock = Lock()

    def save_image(self, *, content: bytes, mime_type: str) -> StoredImageAttachment:
        now = _utc_now()
        attachment = StoredImageAttachment(
            attachment_id=f"attachment-{uuid4()}",
            content=content,
            mime_type=mime_type,
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        with self._lock:
            self._purge_expired(now)
            self._items[attachment.attachment_id] = attachment
        return attachment

    def get_active_image(self, attachment_id: str) -> StoredImageAttachment | None:
        now = _utc_now()
        with self._lock:
            self._purge_expired(now)
            return self._items.get(attachment_id)

    def build_preview_url(self, attachment_id: str) -> str:
        return f"/api/v1/attachments/images/{attachment_id}/preview"

    @staticmethod
    def serialize_expires_at(attachment: StoredImageAttachment) -> str:
        return _utc_iso(attachment.expires_at)

    def _purge_expired(self, now: datetime) -> None:
        expired_ids = [
            attachment_id
            for attachment_id, attachment in self._items.items()
            if attachment.expires_at <= now
        ]
        for attachment_id in expired_ids:
            self._items.pop(attachment_id, None)
