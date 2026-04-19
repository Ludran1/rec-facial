"""
Anti-spoofing pragmático sin modelos ML adicionales.

Usa heurísticas de procesamiento de imagen para detectar:
- Fotos en pantalla (baja nitidez por moiré, brillo uniforme alto)
- Fotos impresas (variación de color baja, textura plana)
- Imágenes muy quietas (no implementado aquí, se hace por sesión en el endpoint)

NO es perfecto: una foto de muy buena calidad podría pasar.
Para producción seria: combinar con un modelo CNN especializado (MiniFASNet, Silent-Face, etc.)
"""
import cv2
import numpy as np


# Umbrales calibrados con pruebas. Ajustar según experiencia real.
SHARPNESS_MIN = 30.0       # rostros muy borrosos = pantalla con moiré
SHARPNESS_MAX = 8000.0     # demasiado nítido = foto impresa muy cerca
COLOR_STD_MIN = 12.0       # variación de color baja = foto plana
HIGHLIGHT_RATIO_MAX = 0.18 # demasiados píxeles brillantes = pantalla


def is_real_face(img_rgb: np.ndarray, bbox: np.ndarray) -> tuple[bool, str]:
    """
    Verifica si el rostro detectado parece real (no una foto).

    Args:
        img_rgb: imagen completa en formato RGB
        bbox: bounding box del rostro [x1, y1, x2, y2]

    Returns:
        (is_real, reason) - reason es vacío si is_real=True
    """
    h, w = img_rgb.shape[:2]
    x1, y1, x2, y2 = bbox.astype(int)
    # Clip a los bordes de la imagen
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return False, "bbox_invalido"

    face_rgb = img_rgb[y1:y2, x1:x2]
    if face_rgb.size == 0:
        return False, "rostro_vacio"

    # Test 1: Nitidez (Laplacian variance)
    gray = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2GRAY)
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    if sharpness < SHARPNESS_MIN:
        return False, f"baja_nitidez ({sharpness:.0f}<{SHARPNESS_MIN})"
    if sharpness > SHARPNESS_MAX:
        return False, f"nitidez_excesiva ({sharpness:.0f}>{SHARPNESS_MAX})"

    # Test 2: Variación de color (fotos impresas son más planas)
    color_std = float(np.std(face_rgb, axis=(0, 1)).mean())
    if color_std < COLOR_STD_MIN:
        return False, f"color_uniforme (std={color_std:.1f}<{COLOR_STD_MIN})"

    # Test 3: Píxeles muy brillantes (pantallas reflejan)
    hsv = cv2.cvtColor(face_rgb, cv2.COLOR_RGB2HSV)
    bright_ratio = float(np.sum(hsv[:, :, 2] > 245)) / hsv[:, :, 2].size
    if bright_ratio > HIGHLIGHT_RATIO_MAX:
        return False, f"reflejos_excesivos ({bright_ratio:.2%}>{HIGHLIGHT_RATIO_MAX:.0%})"

    return True, ""
