import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

FACE_MODEL = os.getenv("FACE_MODEL", "Facenet512")
FACE_THRESHOLD = float(os.getenv("FACE_THRESHOLD", "0.30"))
FACE_DETECTOR = os.getenv("FACE_DETECTOR", "retinaface")

PORT = int(os.getenv("PORT", "8000"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:8080").split(",")]
