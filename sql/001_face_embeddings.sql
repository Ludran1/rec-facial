-- Tabla para almacenar los embeddings faciales de los clientes
-- Cada cliente puede tener múltiples embeddings (3 fotos recomendadas)

CREATE TABLE IF NOT EXISTS public.face_embeddings (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    cliente_id UUID NOT NULL REFERENCES public.clientes(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,

    -- Vector de 512 dimensiones generado por Facenet512
    embedding JSONB NOT NULL,

    -- Metadatos de la foto
    foto_angulo TEXT NOT NULL CHECK (foto_angulo IN ('frontal', 'izquierda', 'derecha')),
    foto_url TEXT,

    -- Modelo usado para generar el embedding
    modelo TEXT NOT NULL DEFAULT 'Facenet512',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_face_embeddings_cliente_id ON public.face_embeddings(cliente_id);
CREATE INDEX IF NOT EXISTS idx_face_embeddings_tenant_id ON public.face_embeddings(tenant_id);

-- RLS: aislar datos por tenant
ALTER TABLE public.face_embeddings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "face_embeddings_tenant_isolation" ON public.face_embeddings
    FOR ALL
    USING (tenant_id = get_auth_tenant_id())
    WITH CHECK (tenant_id = get_auth_tenant_id());

-- Permitir acceso completo al service_role (usado por el backend Python)
CREATE POLICY "face_embeddings_service_role" ON public.face_embeddings
    FOR ALL
    USING (auth.role() = 'service_role');

-- Agregar columna face_registered a clientes para saber si tiene rostro registrado
ALTER TABLE public.clientes
    ADD COLUMN IF NOT EXISTS face_registered BOOLEAN DEFAULT FALSE;
