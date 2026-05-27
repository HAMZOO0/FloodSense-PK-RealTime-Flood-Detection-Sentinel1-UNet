import os
os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")

import cv2
import torch
import numpy as np
from PIL import Image
import io
import albumentations as A
from albumentations.pytorch import ToTensorV2
import segmentation_models_pytorch as smp
import rasterio


# ── Resolve weights ───────────────────────────────────────────
def resolve_weights_path(weights_path=None):
    root       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = []
    if weights_path:
        candidates.append(weights_path)
    candidates.extend([
        os.path.join(root, "models", "best_flood_model.pth"),
        os.path.join(root, "models", "best_model.pth"),
        os.path.join(os.path.dirname(__file__), "best_flood_model.pth"),
        os.path.join(os.path.dirname(__file__), "best_model.pth"),
    ])
    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    raise FileNotFoundError(
        "Model weights not found. Place best_flood_model.pth in models/"
    )


# ── Load model ────────────────────────────────────────────────
def load_flood_model(weights_path=None):
    weights_path = resolve_weights_path(weights_path)
    model = smp.Unet(
        encoder_name="resnet34",
        encoder_weights=None,
        in_channels=3,
        classes=1,
        activation=None
    )
    model.load_state_dict(
        torch.load(weights_path, map_location="cpu", weights_only=False)
    )
    model.eval()
    print(f"Flood model loaded from {weights_path}")
    return model


# ── Preprocess ────────────────────────────────────────────────
def normalize_image(img):
    out    = np.zeros((3, img.shape[1], img.shape[2]), dtype=np.float32)
    out[0] = (np.clip(img[4], -40, 10)  + 40) / 50.0   # VV
    out[1] = (np.clip(img[5], -45, -5)  + 45) / 40.0   # VH
    vv     = out[0] + 1e-8
    vh     = out[1] + 1e-8
    out[2] = np.clip(vh / vv, 0, 2) / 2.0               # ratio
    return np.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0)

def preprocess_image(tif_bytes):
    import io

    with rasterio.open(io.BytesIO(tif_bytes)) as src:
        vv = src.read(1).astype(np.float32)   # (H, W)

    vv = cv2.resize(vv, (256, 256), interpolation=cv2.INTER_LINEAR)

    # Display array for visualization
    display_arr = (np.clip(vv, -25, 0) + 25) / 25.0  # (256, 256) in [0,1]

    # Build 8-ch array so normalize_image() can run (it reads indices 4 & 5)
    img_8ch = np.zeros((8, 256, 256), dtype=np.float32)
    img_8ch[4] = vv   # VV
    img_8ch[5] = vv   # VH approximated with VV

    img_norm = normalize_image(img_8ch)          # → (3, H, W)
    img_norm = np.transpose(img_norm, (1, 2, 0)) # → (H, W, 3)
    img_norm = cv2.resize(img_norm, (256, 256)).astype(np.float32)

    transform = A.Compose([ToTensorV2()])
    tensor = transform(image=img_norm)["image"].unsqueeze(0)  # (1, 3, 256, 256) ✅

    return tensor, display_arr


# ── Predict ───────────────────────────────────────────────────
def predict_flood(model, image_bytes, district_name, bbox):
    """
    Runs U-Net on a GEE SAR tile and returns a full analysis dict.
    """
    tensor, display_arr = preprocess_image(image_bytes)

    with torch.no_grad():
        output = torch.sigmoid(model(tensor))

    pred_np  = output.cpu().numpy()[0, 0]                   # (128, 128)
    pred_256 = cv2.resize(
        pred_np, (256, 256), interpolation=cv2.INTER_LINEAR
    ).astype(np.float32)

    # ── FIX 2: zero out border margin in the prediction ──────────
    # Suppresses edge artifacts caused by encoder zero-padding.
    BORDER = 10   # pixels to suppress at each edge
    pred_256[:BORDER, :]  = 0.0
    pred_256[-BORDER:, :] = 0.0
    pred_256[:, :BORDER]  = 0.0
    pred_256[:, -BORDER:] = 0.0

    pred_prob = pred_256
    pred_mask = pred_prob > 0.5

    # ── Metrics ──────────────────────────────────────────────────
    total_pixels = pred_mask.size
    flood_pixels = int(pred_mask.sum())
    water_pct    = (flood_pixels / total_pixels) * 100

    lon_diff          = bbox[2] - bbox[0]
    lat_diff          = bbox[3] - bbox[1]
    district_area_km2 = lon_diff * lat_diff * 111 * 111
    affected_km2      = district_area_km2 * (water_pct / 100)

    risk_score = min(10, max(1, round(water_pct / 10)))
    risk_label = (
        "low"    if risk_score <= 3 else
        "medium" if risk_score <= 6 else
        "high"
    )

    print(f"  Water coverage : {water_pct:.2f}%")
    print(f"  Affected area  : {affected_km2:.1f} km²")
    print(f"  Risk score     : {risk_score}/10 ({risk_label})")

    return {
        "risk_score":         risk_score,
        "water_coverage_pct": round(water_pct, 2),
        "affected_area_km2":  round(affected_km2, 1),
        "flood_pixels":       flood_pixels,
        "pred_mask":          pred_mask,       # 256×256 bool array
        "pred_prob":          pred_prob,       # 256×256 float array
        "display_arr":        display_arr,     # preprocessed SAR for display
        "settlement_risk":    risk_label,
        "confidence":         "high",
        "model_used":         "U-Net ResNet34 (trained on Pakistan 2022 floods)"
    }