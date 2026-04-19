from fastapi import APIRouter
from app.config import FACE_MODEL, FACE_DETECTOR

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model": FACE_MODEL,
        "detector": FACE_DETECTOR,
    }
