import time
from supabase import create_client, Client

from app.config import SUPABASE_URL, SUPABASE_SERVICE_KEY

_client: Client | None = None

# ── Cache de embeddings por tenant ─────────────────────────────────
# Evita consultar Supabase en cada reconocimiento (cada 3 seg)
CACHE_TTL_SECONDS = 60
_embeddings_cache: dict[str, list[dict]] = {}
_cache_timestamp: dict[str, float] = {}


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


def _is_cache_valid(tenant_id: str) -> bool:
    if tenant_id not in _embeddings_cache:
        return False
    age = time.time() - _cache_timestamp.get(tenant_id, 0)
    return age < CACHE_TTL_SECONDS


def invalidate_tenant_cache(tenant_id: str) -> None:
    """Elimina el cache de un tenant. Forzará re-consulta a Supabase en la próxima petición."""
    _embeddings_cache.pop(tenant_id, None)
    _cache_timestamp.pop(tenant_id, None)
    print(f"[cache] invalidado tenant={tenant_id[:8]}")


def get_embeddings_by_tenant(tenant_id: str) -> list[dict]:
    """
    Obtiene todos los embeddings de un tenant para comparación.
    Usa cache en memoria con TTL para evitar queries repetidas.
    """
    if _is_cache_valid(tenant_id):
        return _embeddings_cache[tenant_id]

    client = get_client()
    result = (
        client.table("face_embeddings")
        .select("id, cliente_id, embedding")
        .eq("tenant_id", tenant_id)
        .execute()
    )
    data = result.data or []

    _embeddings_cache[tenant_id] = data
    _cache_timestamp[tenant_id] = time.time()
    print(f"[cache] refrescado tenant={tenant_id[:8]} con {len(data)} embeddings")

    return data


def get_embeddings_by_cliente(cliente_id: str) -> list[dict]:
    """Obtiene los embeddings de un cliente específico (sin cache, siempre fresco)."""
    client = get_client()
    result = (
        client.table("face_embeddings")
        .select("*")
        .eq("cliente_id", cliente_id)
        .execute()
    )
    return result.data or []


def save_embedding(
    cliente_id: str,
    tenant_id: str,
    embedding: list[float],
    foto_angulo: str,
    foto_url: str | None = None,
    modelo: str = "ArcFace",
) -> dict:
    """Guarda un embedding facial en la base de datos."""
    client = get_client()
    result = (
        client.table("face_embeddings")
        .insert({
            "cliente_id": cliente_id,
            "tenant_id": tenant_id,
            "embedding": embedding,
            "foto_angulo": foto_angulo,
            "foto_url": foto_url,
            "modelo": modelo,
        })
        .execute()
    )

    client.table("clientes").update({"face_registered": True}).eq("id", cliente_id).execute()

    invalidate_tenant_cache(tenant_id)

    return result.data[0] if result.data else {}


def delete_embeddings_by_cliente(cliente_id: str) -> int:
    """Elimina todos los embeddings de un cliente. Retorna cantidad eliminada."""
    client = get_client()

    existing = (
        client.table("face_embeddings")
        .select("tenant_id")
        .eq("cliente_id", cliente_id)
        .limit(1)
        .execute()
    )
    tenant_id = existing.data[0]["tenant_id"] if existing.data else None

    result = (
        client.table("face_embeddings")
        .delete()
        .eq("cliente_id", cliente_id)
        .execute()
    )

    client.table("clientes").update({"face_registered": False}).eq("id", cliente_id).execute()

    if tenant_id:
        invalidate_tenant_cache(tenant_id)

    return len(result.data) if result.data else 0


def get_cliente(cliente_id: str) -> dict | None:
    """Obtiene datos básicos del cliente."""
    client = get_client()
    result = (
        client.table("clientes")
        .select("id, nombre, dni, estado, avatar_url, nombre_membresia, tipo_membresia, fecha_fin, membresia_id, tenant_id, asistencias, face_registered")
        .eq("id", cliente_id)
        .maybeSingle()
        .execute()
    )
    return result.data
