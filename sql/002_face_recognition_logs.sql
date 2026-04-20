-- Audit log de intentos de reconocimiento facial (REC-04)
-- Registra cada llamada al endpoint /api/faces/recognize para:
--   - Debugging ("¿por qué Juan no entró ayer a las 7pm?")
--   - Métricas (tasa de éxito, distribución horaria)
--   - Seguridad (intentos de spoofing, IPs sospechosas)

CREATE TABLE IF NOT EXISTS public.face_recognition_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    cliente_id UUID REFERENCES public.clientes(id) ON DELETE SET NULL,

    -- Resultado del intento
    success BOOLEAN NOT NULL,
    reason TEXT NOT NULL,           -- 'match', 'no_face', 'no_data', 'no_match', 'spoofing_detected'
    detail TEXT,                    -- detalle adicional (motivo del spoofing, etc.)

    -- Métricas de match (solo si hubo intento de comparación)
    distance REAL,                  -- distancia coseno al mejor match (NULL si no hubo)
    confidence REAL,                -- 1.0 - distance (NULL si no hubo)

    -- Contexto opcional
    device_id TEXT,                 -- identificador del kiosko (futuro: multi-kioskos)
    ip_address TEXT,                -- IP del cliente que hizo la request

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para queries comunes
CREATE INDEX IF NOT EXISTS idx_recognition_logs_tenant_created
    ON public.face_recognition_logs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recognition_logs_cliente
    ON public.face_recognition_logs(cliente_id) WHERE cliente_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_recognition_logs_reason
    ON public.face_recognition_logs(tenant_id, reason);

-- RLS: aislar logs por tenant
ALTER TABLE public.face_recognition_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "recognition_logs_tenant_isolation" ON public.face_recognition_logs
    FOR ALL
    USING (tenant_id = get_auth_tenant_id())
    WITH CHECK (tenant_id = get_auth_tenant_id());

CREATE POLICY "recognition_logs_service_role" ON public.face_recognition_logs
    FOR ALL
    USING (auth.role() = 'service_role');
