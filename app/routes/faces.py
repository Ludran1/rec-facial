from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.face_service import extract_embedding, extract_embedding_with_liveness, compare_embeddings, detect_face
from app.services.supabase_service import (
    get_embeddings_by_tenant,
    get_embeddings_by_cliente,
    save_embedding,
    delete_embeddings_by_cliente,
)
from app.utils.image import decode_base64_image

router = APIRouter()


class RegisterRequest(BaseModel):
    cliente_id: str
    tenant_id: str
    image_base64: str
    foto_angulo: str  # "frontal", "izquierda", "derecha"
    foto_url: str | None = None


class RecognizeRequest(BaseModel):
    tenant_id: str
    image_base64: str


class DetectRequest(BaseModel):
    image_base64: str


# ── Registrar rostro ─────────────────────────────────────────────

@router.post("/register")
async def register_face(req: RegisterRequest):
    """Registra un embedding facial para un cliente."""
    if req.foto_angulo not in ("frontal", "izquierda", "derecha"):
        raise HTTPException(400, "foto_angulo debe ser: frontal, izquierda, derecha")

    img = decode_base64_image(req.image_base64)
    embedding = extract_embedding(img)

    if embedding is None:
        raise HTTPException(
            422,
            "No se detectó un rostro en la imagen. Asegúrate de que el rostro esté bien iluminado y visible.",
        )

    # Verificar si ya tiene un embedding con este ángulo
    existing = get_embeddings_by_cliente(req.cliente_id)
    for e in existing:
        if e.get("foto_angulo") == req.foto_angulo:
            raise HTTPException(
                409,
                f"El cliente ya tiene una foto registrada para el ángulo '{req.foto_angulo}'. Elimina primero la existente.",
            )

    saved = save_embedding(
        cliente_id=req.cliente_id,
        tenant_id=req.tenant_id,
        embedding=embedding,
        foto_angulo=req.foto_angulo,
        foto_url=req.foto_url,
    )

    return {
        "success": True,
        "message": f"Rostro registrado ({req.foto_angulo})",
        "embedding_id": saved.get("id"),
        "total_fotos": len(existing) + 1,
    }


# ── Reconocer rostro ─────────────────────────────────────────────

@router.post("/recognize")
async def recognize_face(req: RecognizeRequest):
    """Compara un rostro contra todos los embeddings del tenant."""
    img = decode_base64_image(req.image_base64)
    embedding, status = extract_embedding_with_liveness(img)

    if status == "no_face":
        print("[recognize] sin rostro detectado en la imagen")
        return {
            "recognized": False,
            "reason": "no_face",
            "message": "No se detectó un rostro en la imagen",
        }

    if status.startswith("spoofing_detected"):
        motivo = status.split(":", 1)[1] if ":" in status else "desconocido"
        print(f"[recognize] SPOOFING detectado: {motivo}")
        return {
            "recognized": False,
            "reason": "spoofing_detected",
            "message": "Rostro no válido. Mostrá tu cara real, no una foto.",
            "detail": motivo,
        }

    if embedding is None:
        return {
            "recognized": False,
            "reason": "no_face",
            "message": "No se detectó un rostro en la imagen",
        }

    stored = get_embeddings_by_tenant(req.tenant_id)
    print(f"[recognize] rostro detectado, comparando contra {len(stored)} embeddings almacenados")

    if not stored:
        return {
            "recognized": False,
            "reason": "no_data",
            "message": "No hay rostros registrados para este gimnasio",
        }

    match = compare_embeddings(embedding, stored)

    if match is None:
        # Log para debugging: mostrar la mejor distancia encontrada
        from app.services.face_service import compare_embeddings as _ce
        import numpy as np
        if stored:
            qv = np.array(embedding, dtype=np.float32)
            qn = float(np.linalg.norm(qv))
            best_d = float("inf")
            for s in stored:
                sv = np.array(s["embedding"], dtype=np.float32)
                sn = float(np.linalg.norm(sv))
                if sn == 0 or qn == 0:
                    continue
                cs = float(np.dot(qv, sv) / (qn * sn))
                d = 1.0 - cs
                if d < best_d:
                    best_d = d
            print(f"[recognize] no match - mejor distancia: {best_d:.4f} (threshold actual)")
        return {
            "recognized": False,
            "reason": "no_match",
            "message": "Rostro no reconocido",
        }

    print(f"[recognize] MATCH cliente={match['cliente_id'][:8]} distancia={match['distance']:.4f}")
    return {
        "recognized": True,
        "cliente_id": match["cliente_id"],
        "confidence": round(match["confidence"] * 100, 1),
        "distance": round(match["distance"], 4),
    }


# ── Detectar rostro (sin reconocimiento) ─────────────────────────

@router.post("/detect")
async def detect_face_endpoint(req: DetectRequest):
    """Verifica si hay un rostro detectable en la imagen (para guía en registro)."""
    img = decode_base64_image(req.image_base64)
    detected = detect_face(img)
    return {"detected": detected}


# ── Estado de registro de un cliente ─────────────────────────────

@router.get("/status/{cliente_id}")
async def face_status(cliente_id: str):
    """Retorna cuántas fotos tiene registradas un cliente."""
    embeddings = get_embeddings_by_cliente(cliente_id)
    angulos = [e.get("foto_angulo") for e in embeddings]
    return {
        "cliente_id": cliente_id,
        "total_fotos": len(embeddings),
        "angulos_registrados": angulos,
        "angulos_faltantes": [a for a in ["frontal", "izquierda", "derecha"] if a not in angulos],
        "registro_completo": len(embeddings) >= 3,
    }


# ── Eliminar todos los embeddings de un cliente ──────────────────

@router.delete("/{cliente_id}")
async def delete_faces(cliente_id: str):
    """Elimina todos los embeddings faciales de un cliente."""
    count = delete_embeddings_by_cliente(cliente_id)
    return {
        "success": True,
        "message": f"Se eliminaron {count} embedding(s)",
        "deleted": count,
    }
