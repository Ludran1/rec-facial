import base64
import io
import numpy as np
from PIL import Image


def decode_base64_image(data: str) -> np.ndarray:
    """Convierte una imagen base64 (con o sin prefijo data:image) a numpy array RGB."""
    if "," in data:
        data = data.split(",", 1)[1]

    img_bytes = base64.b64decode(data)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    return np.array(img)
