import base64
import binascii
import io
import numpy as np
from PIL import Image, UnidentifiedImageError


def decode_base64_image(data: str) -> np.ndarray | None:
    """
    Convierte una imagen base64 (con o sin prefijo data:image) a numpy array RGB.
    Retorna None si el input no es base64 válido o no es una imagen reconocible.
    """
    if not data:
        return None
    if "," in data:
        data = data.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(data, validate=False)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        return np.array(img)
    except (binascii.Error, UnidentifiedImageError, ValueError, OSError):
        return None
