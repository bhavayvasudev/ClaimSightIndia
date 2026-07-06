"""Serves user-uploaded profile avatars stored under
`settings.avatar_dir` by `POST /users/me/avatar`.

Public like `/vehicle-images/` and for the same reason: an `<img>` tag
cannot attach an Authorization header. Only avatar objects ever live in
this directory — claim damage photos and policy documents are stored
under `settings.upload_dir` and are never reachable from here. The
filename pattern below matches exactly what the upload route generates
(`u{user_id}-{sha256[:12]}.{ext}`); anything else is a 404.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings

router = APIRouter(prefix="/avatars", tags=["avatars"])

_SAFE_FILENAME = re.compile(r"^u\d{1,12}-[0-9a-f]{12}\.(jpg|png|webp)$")

_MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


@router.get("/{filename}")
async def get_avatar(filename: str) -> FileResponse:
    match = _SAFE_FILENAME.match(filename)
    if not match:
        raise HTTPException(status_code=404, detail="Image not found.")

    directory = Path(get_settings().avatar_dir).resolve()
    path = (directory / filename).resolve()
    # Belt-and-braces: even with the regex above, never serve a file that
    # resolved outside the avatar directory.
    if directory not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")

    return FileResponse(
        path,
        media_type=_MEDIA_TYPES[match.group(1)],
        # Content-addressed filename: the bytes behind a URL never change,
        # so long-lived immutable caching is safe.
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
