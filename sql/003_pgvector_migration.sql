-- REC-07: Migración a pgvector para búsqueda eficiente de embeddings
--
-- ¿Por qué? Antes el backend hacía:
--   1. SELECT * FROM face_embeddings WHERE tenant_id = ...   (fetch de TODOS los embeddings)
--   2. Loop en Python comparando 1 a 1
--
-- Con +1000 clientes esto se vuelve lento (>500ms). Con pgvector + índice IVFFlat
-- la búsqueda se hace en SQL en <50ms incluso con 100k embeddings.
--
-- Estrategia:
--   1. Habilitar extensión pgvector
--   2. Agregar columna embedding_vec (mantenemos el JSONB original por compatibilidad)
--   3. Backfill de datos existentes
--   4. Trigger para sincronizar JSONB → vector en futuros inserts
--   5. Índice IVFFlat para cosine distance
--   6. Función RPC que devuelve el mejor match en 1 query

-- 1. Habilitar pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Columna vector(512) — InsightFace ArcFace produce embeddings de 512 dims
ALTER TABLE public.face_embeddings
    ADD COLUMN IF NOT EXISTS embedding_vec vector(512);

-- 3. Backfill desde la columna JSONB existente
UPDATE public.face_embeddings
SET embedding_vec = embedding::text::vector
WHERE embedding_vec IS NULL AND embedding IS NOT NULL;

-- 4. Trigger para mantener sincronizadas las columnas
--    (el backend sigue insertando en `embedding` JSONB sin cambios)
CREATE OR REPLACE FUNCTION sync_face_embedding_vec()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.embedding IS NOT NULL THEN
        NEW.embedding_vec = NEW.embedding::text::vector;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sync_face_embedding_vec_trigger ON public.face_embeddings;
CREATE TRIGGER sync_face_embedding_vec_trigger
    BEFORE INSERT OR UPDATE OF embedding ON public.face_embeddings
    FOR EACH ROW
    EXECUTE FUNCTION sync_face_embedding_vec();

-- 5. Índice IVFFlat para cosine distance
--    `lists` ideal: sqrt(filas). Para hasta ~10k embeddings, lists=100 está bien.
--    Si crece a 100k, recrear con lists=316.
CREATE INDEX IF NOT EXISTS idx_face_embeddings_vec_cosine
    ON public.face_embeddings
    USING ivfflat (embedding_vec vector_cosine_ops)
    WITH (lists = 100);

-- 6. Función RPC: devuelve el embedding más cercano dentro del tenant
--    El backend decide si la distancia está dentro del threshold
CREATE OR REPLACE FUNCTION match_face_embedding(
    query_embedding vector(512),
    query_tenant_id uuid
)
RETURNS TABLE (
    cliente_id uuid,
    distance double precision
)
LANGUAGE sql
SECURITY DEFINER
AS $$
    SELECT
        fe.cliente_id,
        (fe.embedding_vec <=> query_embedding)::double precision AS distance
    FROM public.face_embeddings fe
    WHERE fe.tenant_id = query_tenant_id
      AND fe.embedding_vec IS NOT NULL
    ORDER BY fe.embedding_vec <=> query_embedding ASC
    LIMIT 1;
$$;

GRANT EXECUTE ON FUNCTION match_face_embedding TO service_role;
GRANT EXECUTE ON FUNCTION match_face_embedding TO authenticated;
