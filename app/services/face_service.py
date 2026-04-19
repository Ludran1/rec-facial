import numpy as np
from insightface.app import FaceAnalysis

from app.config import FACE_THRESHOLD

_app: FaceAnalysis | None = None


def preload_model():
    """Pre-carga el modelo buffalo_l (ArcFace + RetinaFace ONNX) en memoria."""
    global _app
    if _app is not None:
        return
    _app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    _app.prepare(ctx_id=-1, det_size=(640, 640))
    print("InsightFace buffalo_l (ArcFace + RetinaFace) cargado en memoria")


def _get_app() -> FaceAnalysis:
    if _app is None:
        preload_model()
    return _app  # type: ignore[return-value]


def _largest_face(faces):
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def extract_embedding(img: np.ndarray) -> list[float] | None:
    """
    Extrae el embedding facial del rostro más grande detectado.
    img: numpy array RGB (como sale de PIL)
    Retorna None si no se detecta un rostro.
    """
    img_bgr = img[:, :, ::-1]  # InsightFace espera BGR
    app = _get_app()
    faces = app.get(img_bgr)
    if not faces:
        return None
    face = _largest_face(faces)
    return face.embedding.tolist()


def compare_embeddings(
    embedding: list[float],
    stored_embeddings: list[dict],
) -> dict | None:
    """
    Compara un embedding contra una lista de embeddings almacenados.
    Retorna el mejor match si está dentro del umbral, o None.
    """
    if not stored_embeddings:
        return None

    query_vec = np.array(embedding, dtype=np.float32)
    query_norm = float(np.linalg.norm(query_vec))
    if query_norm == 0:
        return None

    best_match = None
    best_distance = float("inf")

    for stored in stored_embeddings:
        stored_vec = np.array(stored["embedding"], dtype=np.float32)
        stored_norm = float(np.linalg.norm(stored_vec))
        if stored_norm == 0:
            continue
        cosine_sim = float(np.dot(query_vec, stored_vec) / (query_norm * stored_norm))
        distance = 1.0 - cosine_sim

        if distance < best_distance:
            best_distance = distance
            best_match = stored

    if best_match is None or best_distance > FACE_THRESHOLD:
        return None

    return {
        "cliente_id": best_match["cliente_id"],
        "distance": float(best_distance),
        "confidence": float(1.0 - best_distance),
    }


def detect_face(img: np.ndarray) -> bool:
    """Verifica si hay al menos un rostro detectable."""
    img_bgr = img[:, :, ::-1]
    app = _get_app()
    faces = app.get(img_bgr)
    return len(faces) > 0
