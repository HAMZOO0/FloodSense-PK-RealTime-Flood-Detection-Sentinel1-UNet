"""U-Net flood model singleton — loaded once per process, thread-safe."""

import logging
import threading

from ..errors import service_unavailable

logger = logging.getLogger("floodsense.model")

_lock = threading.Lock()
_model = None
_load_error: str = ""


def get_model():
    """Load (once) and return the U-Net ResNet34 flood model."""
    global _model, _load_error
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        try:
            from models.model_inference import load_flood_model

            _model = load_flood_model()
            _load_error = ""
            logger.info("U-Net flood model loaded.")
            return _model
        except FileNotFoundError as e:
            _load_error = str(e)
            raise service_unavailable(
                "MODEL_WEIGHTS_MISSING",
                "U-Net weights not found — place best_flood_model.pth in models/.",
            )
        except Exception as e:
            _load_error = str(e)
            raise service_unavailable(
                "MODEL_LOAD_FAILED", f"Could not load the flood model: {e}"
            )


def model_status() -> dict:
    return {"loaded": _model is not None, "error": _load_error or None}
