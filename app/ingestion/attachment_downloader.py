"""Attachment binary download boundary for extraction workers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.schemas.page_object import Attachment

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class DownloadedAttachment:
    """Downloaded attachment bytes plus the local path used by downstream chunkers."""

    content: bytes
    local_path: str


class AttachmentDownloader(Protocol):
    """Downloads or resolves an attachment binary for extraction."""

    def download(self, attachment: Attachment) -> DownloadedAttachment:
        """Return attachment bytes and a readable local path."""


@dataclass(slots=True)
class DefaultAttachmentDownloader:
    """Default downloader supporting existing local files, ``file://`` URIs, and HTTP(S)."""

    download_dir: str = "data/attachments"
    access_token: str | None = None
    timeout_seconds: int = 20

    def download(self, attachment: Attachment) -> DownloadedAttachment:
        if attachment.local_path:
            path = Path(attachment.local_path)
            return DownloadedAttachment(content=path.read_bytes(), local_path=str(path))

        parsed = urlparse(attachment.download_url)
        if parsed.scheme == "file":
            path = Path(parsed.path)
            return DownloadedAttachment(content=path.read_bytes(), local_path=str(path))
        if parsed.scheme in {"http", "https"}:
            return self._download_http(attachment)

        path = Path(attachment.download_url)
        return DownloadedAttachment(content=path.read_bytes(), local_path=str(path))

    def _download_http(self, attachment: Attachment) -> DownloadedAttachment:
        headers = {}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = Request(attachment.download_url, headers=headers)
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            content = response.read()

        target = Path(self.download_dir) / _safe_download_name(attachment)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return DownloadedAttachment(content=content, local_path=str(target))


def _safe_download_name(attachment: Attachment) -> str:
    suffix = Path(attachment.filename).suffix
    stem = _SAFE_NAME_RE.sub("_", attachment.attachment_id).strip("._") or "attachment"
    return f"{stem}{suffix}"
