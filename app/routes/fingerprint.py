import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import fingerprint_service as fs
from app.services.supabase_service import (
    get_fingerprints_by_tenant,
    save_fingerprint,
    delete_fingerprint_by_cliente,
    get_cliente,
    save_recognition_log,
)

router = APIRouter()


class EnrollRequest(BaseModel):
    cliente_id: str
    tenant_id: str
    template1: str
    template2: str
    template3: str


class IdentifyRequest(BaseModel):
    tenant_id: str


class CaptureRequest(BaseModel):
    timeout: int = 15


@router.get("/device")
async def device_status():
    """Verifica si el lector ZKTeco está conectado."""
    return fs.device_status()


@router.post("/capture")
async def capture_fingerprint(req: CaptureRequest):
    """
    Captura una huella del lector.
    Bloquea hasta que el usuario apoya el dedo o pasa el timeout.
    """
    template = await asyncio.to_thread(fs.capture_one, req.timeout)
    if template is None:
        raise HTTPException(408, "Tiempo agotado. No se detectó ninguna huella.")
    return {"template": template}


@router.post("/enroll")
async def enroll_fingerprint(req: EnrollRequest):
    """
    Combina 3 capturas en un template final y lo guarda en Supabase.
    """
    try:
        merged = await asyncio.to_thread(
            fs.merge_three, req.template1, req.template2, req.template3
        )
    except Exception as e:
        raise HTTPException(500, f"Error al combinar huellas: {e}")

    result = save_fingerprint(req.cliente_id, req.tenant_id, merged)
    if not result:
        raise HTTPException(500, "Error al guardar la huella en la base de datos")
    return {"ok": True}


@router.post("/identify")
async def identify_fingerprint(req: IdentifyRequest):
    """
    Carga todos los templates del tenant e intenta identificar la huella.
    Si hay match, registra la asistencia.
    """
    templates = get_fingerprints_by_tenant(req.tenant_id)
    if not templates:
        raise HTTPException(404, "No hay huellas registradas para este gimnasio")

    match = await asyncio.to_thread(fs.identify_from_templates, templates, 15)

    if match is None:
        save_recognition_log(
            tenant_id=req.tenant_id,
            success=False,
            reason="fingerprint_not_matched",
        )
        raise HTTPException(404, "Huella no reconocida")

    cliente = get_cliente(match["cliente_id"])
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    save_recognition_log(
        tenant_id=req.tenant_id,
        success=True,
        reason="fingerprint_match",
        cliente_id=match["cliente_id"],
        confidence=match["score"] / 100.0,
    )

    return {
        "ok": True,
        "cliente_id": match["cliente_id"],
        "nombre": cliente["nombre"],
        "estado": cliente["estado"],
        "nombre_membresia": cliente.get("nombre_membresia"),
        "fecha_fin": cliente.get("fecha_fin"),
        "avatar_url": cliente.get("avatar_url"),
        "score": match["score"],
    }


@router.delete("/delete/{cliente_id}")
async def delete_fingerprint(cliente_id: str):
    """Elimina la huella de un cliente."""
    deleted = delete_fingerprint_by_cliente(cliente_id)
    return {"ok": True, "deleted": deleted}
