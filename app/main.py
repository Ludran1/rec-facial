from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import CORS_ORIGINS
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

app.include_router(health_router, prefix="/api")
app.include_router(faces_router, prefix="/api/faces")


@app.on_event("startup")
async def startup():
    """Pre-carga el modelo al iniciar para que la primera petición sea rápida."""
    preload_model()
