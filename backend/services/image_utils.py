import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Dict

from PIL import Image


SUPPORTED_FORMATS: Dict[str, str] = {
    "JPEG": "image/jpeg",
    "JPG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


@dataclass
class PreparedImage:
    image_bytes: bytes
    content_type: str
    data_uri: str
    image_format: str


def decode_base64_image(encoded: str) -> bytes:
    """Decode a base64 image string, stripping any data URL prefix."""
    if "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        return base64.b64decode(encoded)
    except Exception as exc:
        raise ValueError("Invalid base64 image data") from exc


def prepare_image(image_data: bytes, max_size_mb: int = 10) -> PreparedImage:
    """Validate and normalize an image for analysis and upload."""
    size_mb = len(image_data) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"Image too large: {size_mb:.2f}MB (max {max_size_mb}MB)")

    try:
        image = Image.open(BytesIO(image_data))
        image.verify()
    except Exception as exc:
        raise ValueError("Invalid image file") from exc

    # Re-open after verify because verify() can close the file
    image = Image.open(BytesIO(image_data))

    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background

    fmt = (image.format or "JPEG").upper()
    fmt = "JPEG" if fmt == "JPG" else fmt
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image format: {fmt}")

    buffer = BytesIO()
    image.save(buffer, format=fmt)
    processed_bytes = buffer.getvalue()

    content_type = SUPPORTED_FORMATS[fmt]
    encoded = base64.b64encode(processed_bytes).decode()
    data_uri = f"data:{content_type};base64,{encoded}"

    return PreparedImage(
        image_bytes=processed_bytes,
        content_type=content_type,
        data_uri=data_uri,
        image_format=fmt,
    )
