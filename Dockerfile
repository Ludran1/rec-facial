FROM python:3.11-slim

# Dependencias del sistema para OpenCV y DeepFace
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-descargar el modelo Facenet512 durante el build
RUN python -c "from deepface import DeepFace; import numpy as np; DeepFace.represent(np.zeros((224,224,3), dtype=np.uint8), model_name='Facenet512', detector_backend='opencv', enforce_detection=False)" || true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
