"""Serves the locally-stored reference vehicle images that
`app/services/vehicle_reference.py` resolves and persists under
`settings.vehicle_image_dir`.

Deliberately public (no bearer token): these are generic, non-user
images of vehicle model lines — they carry no claim data, no user data,
and their filenames are content-addressed slugs, not claim identifiers.
An `<img>` tag cannot attach an Authorization header, so requiring one
here would just break rendering without protecting anything.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings

router = APIRouter(prefix="/vehicle-images", tags=["vehicle-images"])

# Content-addressed filenames produced by store_vehicle_image() only —
# anything else (path separators, dots, traversal) is rejected outright.
_SAFE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,120}\.(jpg|png|webp)$")

_MEDIA_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}


@router.get("/{filename}")
async def get_vehicle_image(filename: str) -> FileResponse:
    match = _SAFE_FILENAME.match(filename)
    if not match:
        raise HTTPException(status_code=404, detail="Image not found.")

    directory = Path(get_settings().vehicle_image_dir).resolve()
    path = (directory / filename).resolve()
    # Belt-and-braces: even with the regex above, never serve a file that
    # resolved outside the image directory.
    if directory not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Image not found.")

    return FileResponse(
        path,
        media_type=_MEDIA_TYPES[match.group(1)],
        # Content-addressed filename: the bytes behind a URL never change,
        # so long-lived immutable caching is safe.
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
