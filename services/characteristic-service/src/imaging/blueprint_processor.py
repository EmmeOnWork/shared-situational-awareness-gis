"""Server-side Blueprint image processing — isolated from HTTP and the DB.

``process_blueprint(bytes, content_type) -> ProcessedBlueprint`` is the single
seam every stored Blueprint passes through (slice 5). It keeps stored plans
**bounded** (a finalised byte cap) and **legible** (a generous longest-edge cap
with LANCZOS resampling, which preserves the thin black lines of engineering
drawings instead of washing them out). Bytes in, processed bytes out; a malformed
or unsupported raster is rejected with a domain error the router maps to 415 —
there is no HTTP or database knowledge here.
"""

import io
from dataclasses import dataclass

from PIL import Image, UnidentifiedImageError

from src.config import get_settings

# The raster formats a Blueprint may be stored as. The *real* decoded format
# (Pillow's ``img.format``) is authoritative — not the caller's declared
# content_type — so a mislabelled or corrupt upload cannot slip through.
_FORMAT_CONTENT_TYPES = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    # AVIF is common for images saved off the web (CDNs serve it, often keeping a
    # .png/.jpg name + content_type). Pillow decodes AND re-encodes it here, so it is
    # accepted like the rest; the stored content_type is the real decoded one.
    "AVIF": "image/avif",
}

# The content_types a Blueprint may be uploaded as — the single source of truth the
# router reuses for its cheap pre-decode reject (a wrong *declared* type fails fast,
# before the bytes are even decoded here).
SUPPORTED_CONTENT_TYPES = frozenset(_FORMAT_CONTENT_TYPES.values())


class BlueprintRejected(Exception):
    """Base for a Blueprint the processor refuses (router maps it to a 4xx)."""


class UnsupportedImageFormat(BlueprintRejected):
    """The bytes do not decode as one of the supported raster formats."""


@dataclass(frozen=True)
class ProcessedBlueprint:
    """The bytes to store plus their authoritative ``content_type``."""

    image: bytes
    content_type: str


def process_blueprint(image: bytes, content_type: str) -> ProcessedBlueprint:
    """Validate, downscale and size-cap a Blueprint upload. ``content_type`` is
    the caller's *declared* type and is only a hint — the stored type is derived
    from the bytes' real decoded format."""
    img = _decode(image)
    fmt = img.format
    content_type = _FORMAT_CONTENT_TYPES[fmt]
    settings = get_settings()
    max_dim = settings.max_blueprint_dimension
    cap = settings.finalised_blueprint_bytes

    # Already bounded both ways → store the exact uploaded bytes (no needless
    # re-encode that could add artifacts).
    if max(img.size) <= max_dim and len(image) <= cap:
        return ProcessedBlueprint(image=image, content_type=content_type)

    working = img
    if max(working.size) > max_dim:
        working = _scale_longest_edge(working, max_dim)
    encoded = _encode(working, fmt)

    # Keep shrinking until the re-encoded bytes fit the finalised cap. Each step
    # trims the longest edge ~15%; dimensions strictly decrease, so this always
    # terminates and the output ALWAYS respects the cap.
    while len(encoded) > cap and max(working.size) > 1:
        longest = max(working.size)
        working = _scale_longest_edge(working, max(1, min(longest - 1, int(longest * 0.85))))
        encoded = _encode(working, fmt)

    return ProcessedBlueprint(image=encoded, content_type=content_type)


def _scale_longest_edge(img: Image.Image, longest: int) -> Image.Image:
    """Downscale ``img`` so its longest edge is ``longest`` px, keeping aspect
    ratio. LANCZOS is the documented resampling choice: it preserves the thin
    black-and-white lines of engineering plans instead of blurring them away."""
    width, height = img.size
    scale = longest / max(width, height)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _encode(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _decode(image: bytes) -> Image.Image:
    """Open the bytes as a supported raster, or reject. Decoding here is the
    hardened format check: declared content_type is never trusted."""
    try:
        img = Image.open(io.BytesIO(image))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise UnsupportedImageFormat(
            "The upload is not a readable image."
        ) from exc
    if img.format not in _FORMAT_CONTENT_TYPES:
        allowed = ", ".join(sorted(_FORMAT_CONTENT_TYPES.values()))
        raise UnsupportedImageFormat(
            f"Unsupported image format '{img.format}'. Allowed: {allowed}."
        )
    return img
