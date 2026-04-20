from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.services.face_service import extract_embedding, extract_embedding_with_liveness, compare_embeddings, detect_face
from app.services.supabase_service import (
    get_embeddings_by_tenant,
    get_embeddings_by_cliente,
    save_embedding,
    delete_embeddings_by_cliente,
    delete_embedding_by_angle,
    save_recognition_log,
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
    device_id: str | None = None


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

    # Si ya existe un embedding con este ángulo, lo sobrescribimos (idempotente)
    existing = get_embeddings_by_cliente(req.cliente_id)
    angulo_existente = any(e.get("foto_angulo") == req.foto_angulo for e in existing)
    accion = "actualizado" if angulo_existente else "registrado"

    if angulo_existente:
        delete_embedding_by_angle(req.cliente_id, req.foto_angulo)

    saved = save_embedding(
        cliente_id=req.cliente_id,
        tenant_id=req.tenant_id,
        embedding=embedding,
        foto_angulo=req.foto_angulo,
        foto_url=req.foto_url,
    )

    total_fotos = len(existing) + (0 if angulo_existente else 1)

    return {
        "success": True,
        "message": f"Rostro {accion} ({req.foto_angulo})",
        "embedding_id": saved.get("id"),
        "total_fotos": total_fotos,
        "updated": angulo_existente,
    }


# ── Reconocer rostro ─────────────────────────────────────────────

@router.post("/recognize")
async def recognize_face(req: RecognizeRequest, request: Request):
    """Compara un rostro contra todos los embeddings del tenant."""
    ip = request.client.host if request.client else None
    img = decode_base64_image(req.image_base64)
    embedding, status = extract_embedding_with_liveness(img)

    if status == "no_face":
        print("[recognize] sin rostro detectado en la imagen")
        save_recognition_log(
            tenant_id=req.tenant_id, success=False, reason="no_face",
            device_id=req.device_id, ip_address=ip,
        )
        return {
            "recognized": False,
            "reason": "no_face",
            "message": "No se detectó un rostro en la imagen",
        }

    if status.startswith("spoofing_detected"):
        motivo = status.split(":", 1)[1] if ":" in status else "desconocido"
        print(f"[recognize] SPOOFING detectado: {motivo}")
        save_recognition_log(
            tenant_id=req.tenant_id, success=False, reason="spoofing_detected",
            detail=motivo, device_id=req.device_id, ip_address=ip,
        )
        return {
            "recognized": False,
            "reason": "spoofing_detected",
            "message": "Rostro no válido. Mostrá tu cara real, no una foto.",
            "detail": motivo,
        }

    if embedding is None:
        save_recognition_log(
            tenant_id=req.tenant_id, success=False, reason="no_face",
            device_id=req.device_id, ip_address=ip,
        )
        return {
            "recognized": False,
            "reason": "no_face",
            "message": "No se detectó un rostro en la imagen",
        }

    stored = get_embeddings_by_tenant(req.tenant_id)
    print(f"[recognize] rostro detectado, comparando contra {len(stored)} embeddings almacenados")

    if not stored:
        save_recognition_log(
            tenant_id=req.tenant_id, success=False, reason="no_data",
            device_id=req.device_id, ip_address=ip,
        )
        return {
            "recognized": False,
            "reason": "no_data",
            "message": "No hay rostros registrados para este gimnasio",
        }

    match = compare_embeddings(embedding, stored)

    if match is None:
        # Calcular mejor distancia para log y debugging
        import numpy as np
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
        save_recognition_log(
            tenant_id=req.tenant_id, success=False, reason="no_match",
            distance=best_d if best_d != float("inf") else None,
            device_id=req.device_id, ip_address=ip,
        )
        return {
            "recognized": False,
            "reason": "no_match",
            "message": "Rostro no reconocido",
        }

    print(f"[recognize] MATCH cliente={match['cliente_id'][:8]} distancia={match['distance']:.4f}")
    save_recognition_log(
        tenant_id=req.tenant_id, success=True, reason="match",
        cliente_id=match["cliente_id"],
        distance=match["distance"], confidence=match["confidence"],
        device_id=req.device_id, ip_address=ip,
    )
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
