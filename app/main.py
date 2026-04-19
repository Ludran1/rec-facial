from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import CORS_ORIGINS, FACE_API_KEY
from app.routes.faces import router as faces_router
from app.routes.health import router as health_router
from app.services.face_service import preload_model

app = FastAPI(title="FitGym - Reconocimiento Facial", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Rutas que NO requieren autenticación (health checks, docs, root)
PUBLIC_PATHS = {"/api/health", "/", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    """
    Valida el header X-API-Key contra FACE_API_KEY del .env.
    Si FACE_API_KEY está vacío en config (modo dev), no valida nada.
    Las rutas en PUBLIC_PATHS siempre pasan.
    """
    # Permitir CORS preflight
    if request.method == "OPTIONS":
        return await call_next(request)

    # Si no hay API key configurada en backend, modo "sin auth"
    if not FACE_API_KEY:
        return await call_next(request)

    # Permitir rutas públicas (healthcheck, docs)
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)

    # Validar header
    provided_key = request.headers.get("x-api-key", "")
    if provided_key != FACE_API_KEY:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing X-API-Key header"},
        )

    return await call_next(request)


app.include_router(health_router, prefix="/api")
app.include_router(faces_router, prefix="/api/faces")


@app.on_event("startup")
async def startup():
    """Pre-carga el modelo al iniciar para que la primera petición sea rápida."""
    preload_model()
