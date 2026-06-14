"""Unit tests for the isolated Blueprint image-processor (slice 5).

The module is pure-ish: ``bytes + declared content_type`` in, processed
``bytes + content_type`` out (or a rejection). No HTTP, no DB — so these tests
call it directly with real raster bytes built by Pillow.
"""

import io
import os

import pytest
from PIL import Image, ImageDraw, features

from src.config import get_settings
from src.imaging.blueprint_processor import (
    UnsupportedImageFormat,
    process_blueprint,
)


def _noise_png(width: int, height: int) -> bytes:
    """A high-entropy image that does not compress to near-nothing, so a small
    finalised cap actually forces a shrink."""
    img = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    return _encode(img, "PNG")


def _encode(img: Image.Image, fmt: str) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _png(width: int, height: int, color=(255, 255, 255)) -> bytes:
    return _encode(Image.new("RGB", (width, height), color), "PNG")


def test_undecodable_bytes_are_rejected():
    """Format validation is decode-based, not declared-type trust: bytes that do
    not open as a supported raster are rejected even when the caller *declares* an
    image type. This is the hardening over slice 3's content-type-only check."""
    with pytest.raises(UnsupportedImageFormat):
        process_blueprint(b"%PDF-1.4 not an image at all", "image/png")


def test_in_bounds_image_is_accepted_and_round_trips():
    """A small, valid raster within both caps comes back decodable, with the
    content_type taken from the *real* decoded format — not whatever the caller
    declared (here a deliberately wrong ``image/webp`` hint over PNG bytes)."""
    result = process_blueprint(_png(800, 600), "image/webp")

    assert result.content_type == "image/png"
    out = Image.open(io.BytesIO(result.image))
    assert out.size == (800, 600)
    assert out.format == "PNG"


@pytest.mark.skipif(not features.check("avif"), reason="Pillow built without AVIF here")
def test_avif_image_is_accepted_and_round_trips():
    """AVIF is a supported format (web images are frequently AVIF even when named
    .png): a valid AVIF raster is accepted and its stored content_type is the real
    decoded one — ``image/avif`` — regardless of the declared (here wrong) hint. The
    service image ships Pillow with AVIF; a dev box without it skips this."""
    result = process_blueprint(_encode(Image.new("RGB", (800, 600), (255, 255, 255)), "AVIF"), "image/png")

    assert result.content_type == "image/avif"
    out = Image.open(io.BytesIO(result.image))
    assert out.format == "AVIF"


def test_oversized_dimensions_are_downscaled_to_the_cap():
    """An image past the longest-edge cap (2400px) is downscaled: the longest edge
    lands on the cap and the aspect ratio is kept, so storage stays bounded and the
    plan is not stored at phone-photo resolution."""
    original = _png(4800, 1200)

    result = process_blueprint(original, "image/png")

    out = Image.open(io.BytesIO(result.image))
    assert max(out.size) == 2400
    assert out.size == (2400, 600)  # aspect ratio preserved
    assert len(result.image) < len(original)


def test_output_is_shrunk_to_fit_the_finalised_byte_cap(monkeypatch):
    """Even an image whose dimensions are already within the longest-edge cap is
    shrunk further until its re-encoded bytes fit under the finalised byte cap, so
    a stored Blueprint ALWAYS respects the cap (never rejected for size)."""
    get_settings.cache_clear()
    monkeypatch.setenv("FINALISED_BLUEPRINT_BYTES", "40000")
    try:
        original = _noise_png(2000, 2000)  # within 2400px, but far over 40 KB
        result = process_blueprint(original, "image/png")
    finally:
        get_settings.cache_clear()

    assert len(result.image) <= 40000
    out = Image.open(io.BytesIO(result.image))
    assert max(out.size) < 2000  # it had to shrink despite being in-bounds


def test_thin_lines_survive_the_downscale():
    """The legibility guarantee: thin black lines on white (an engineering plan)
    are still clearly dark after the downscale — LANCZOS keeps them, where a naive
    blurring shrink would wash them toward the white background."""
    img = Image.new("RGB", (4800, 400), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    for x in range(0, 4800, 8):  # thin (2px) vertical lines on white
        draw.rectangle([x, 0, x + 1, 400], fill=(0, 0, 0))
    original = _encode(img, "PNG")

    result = process_blueprint(original, "image/png")

    out = Image.open(io.BytesIO(result.image)).convert("L")
    assert max(out.size) == 2400  # downscaled
    extrema_min, extrema_max = out.getextrema()
    assert extrema_min < 128  # lines stayed dark, not washed out
    assert extrema_max > 200  # white background preserved (real contrast remains)
