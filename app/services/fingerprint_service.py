"""
Servicio ZKTeco para lector de huellas dactilares.
Requiere: pip install pyzkfp
Y el ZKFinger SDK instalado en Windows (ZKFinger_x64.dll).
"""
import base64
import threading
import time
from typing import Optional

_zkfp2 = None
_lock = threading.Lock()


def _get_sdk():
    global _zkfp2
    if _zkfp2 is not None:
        return _zkfp2
    try:
        from pyzkfp import ZKFP2
        sdk = ZKFP2()
        ret = sdk.Init()
        if ret != 0:
            raise RuntimeError(f"ZKFinger SDK Init error: {ret}")
        count = sdk.GetDeviceCount()
        if count == 0:
            raise RuntimeError("No se encontró ningún lector de huellas conectado")
        ret = sdk.OpenDevice(0)
        if ret != 0:
            raise RuntimeError(f"No se pudo abrir el dispositivo: {ret}")
        _zkfp2 = sdk
        print("[fingerprint] dispositivo ZKTeco inicializado")
        return _zkfp2
    except ImportError:
        raise RuntimeError("pyzkfp no está instalado. Ejecutá: pip install pyzkfp")


def device_status() -> dict:
    try:
        _get_sdk()
        return {"connected": True}
    except Exception as e:
        return {"connected": False, "error": str(e)}


def capture_one(timeout_sec: int = 15) -> Optional[str]:
    """Captura una huella. Retorna template en base64 o None si timeout."""
    with _lock:
        sdk = _get_sdk()
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            tmp, img = sdk.AcquireFingerprint()
            if tmp:
                return base64.b64encode(tmp).decode()
            time.sleep(0.08)
        return None


def merge_three(t1_b64: str, t2_b64: str, t3_b64: str) -> str:
    """Combina 3 capturas en un template de registro final."""
    with _lock:
        sdk = _get_sdk()
        t1 = base64.b64decode(t1_b64)
        t2 = base64.b64decode(t2_b64)
        t3 = base64.b64decode(t3_b64)
        merged, _ = sdk.DBMerge(t1, t2, t3)
        if not merged:
            raise RuntimeError("No se pudo combinar los templates. Intentá de nuevo.")
        return base64.b64encode(merged).decode()


def identify_from_templates(templates: list[dict], timeout_sec: int = 15) -> Optional[dict]:
    """
    Carga los templates en el SDK e intenta identificar una huella.
    templates: lista de {"uid": int, "cliente_id": str, "template": base64_str}
    Retorna {"cliente_id": str, "score": int} o None.
    """
    with _lock:
        sdk = _get_sdk()
        sdk.DBFree()

        uid_to_cliente = {}
        for item in templates:
            uid = item["uid"]
            template = base64.b64decode(item["template"])
            sdk.DBAdd(uid, template)
            uid_to_cliente[uid] = item["cliente_id"]

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            tmp, img = sdk.AcquireFingerprint()
            if tmp:
                uid, score = sdk.DBIdentify(tmp)
                if uid >= 0:
                    cliente_id = uid_to_cliente.get(uid)
                    if cliente_id:
                        return {"cliente_id": cliente_id, "score": int(score)}
            time.sleep(0.08)
        return None
