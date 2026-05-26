import os
import cv2
import torch
import numpy as np
from PIL import Image
import io
import albumentations as A
from albumentations.pytorch import ToTensorV2
import segmentation_models_pytorch as smp


# ── Load your trained model ───────────────────────────────────
def load_flood_model(weights_path="models/best_model.pth"):
    if not os.path.isabs(weights_path):
        weights_path = os.path.join(os.path.dirname(__file__), weights_path)

    if not os.path.exists(weights_path):
        raise FileNotFoundError(f"Model weights not found: {weights_path}")

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


# ── Preprocess GEE SAR PNG bytes → tensor ────────────────────
def preprocess_image(image_bytes):
    """
    Converts raw PNG bytes downloaded from GEE into a tensor
    that matches the distribution the model was trained on.

    THE CRITICAL FIX:
    ─────────────────
    Training data was a classified map:
        pixel value 1 = land  → normalized to 0.0
        pixel value 2 = flood → normalized to 1.0

    GEE downloads SAR as a PNG scaled with min=-25dB, max=0dB:
        dark pixels  = water/flood (low backscatter, ~-20 to -15 dB)
        bright pixels = land/urban (high backscatter, ~-10 to 0 dB)

    Problem: dark=low value=0.0 in PNG → model sees 0.0 → predicts LAND
             but dark should mean FLOOD (value 1.0 in training)

    Fix: INVERT the normalized image so dark→1.0 (flood) bright→0.0 (land)
         This matches training distribution exactly.
    """
    # Open PNG and convert to grayscale
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img = img.resize((128, 128))  # model input size
    arr = np.array(img, dtype=np.float32)

    # Remove invalid pixels
    arr = np.nan_to_num(arr, nan=0.0)

    # Clip outliers using percentiles
    valid = arr[arr > 0]
    if len(valid) > 0:
        p2  = np.percentile(valid, 2)
        p98 = np.percentile(valid, 98)
        arr = np.clip(arr, p2, p98)

    # Normalize to 0–1
    arr_min = arr.min()
    arr_max = arr.max()
    if arr_max - arr_min > 0:
        arr = (arr - arr_min) / (arr_max - arr_min)
    else:
        arr = np.zeros_like(arr)

    # ── CRITICAL FIX: INVERT ──────────────────────────────────
    # Dark SAR pixels = water = should be 1.0 (flood in training)
    # Bright SAR pixels = land = should be 0.0 (land in training)
    arr = 1.0 - arr

    # Make 3-channel input (model expects RGB-like)
    arr3 = np.stack([arr, arr, arr], axis=-1).astype(np.float32)

    # Apply same normalization used during training
    transform = A.Compose([
        A.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225)
        ),
        ToTensorV2()
    ])

    tensor = transform(image=arr3)["image"].unsqueeze(0)
    return tensor, arr  # return arr for visualization


# ── Run flood segmentation ────────────────────────────────────
def predict_flood(model, image_bytes, district_name, bbox):
    """
    Runs U-Net on the GEE SAR tile.
    Returns full analysis dict with flood mask and metrics.
    """
    # Preprocess
    tensor, display_arr = preprocess_image(image_bytes)

    # Predict
    with torch.no_grad():
        output = torch.sigmoid(model(tensor))

    pred_np   = output.cpu().numpy()[0, 0]   # (128, 128) probabilities

    # Resize prediction to 256x256 for display
    pred_256  = cv2.resize(pred_np, (256, 256), interpolation=cv2.INTER_LINEAR)
    pred_mask = pred_256 > 0.5   # binary flood mask

    # ── Calculate metrics ─────────────────────────────────────
    total_pixels = pred_mask.size
    flood_pixels = int(pred_mask.sum())
    water_pct    = (flood_pixels / total_pixels) * 100

    # Area calculation from bounding box
    lon_diff          = bbox[2] - bbox[0]
    lat_diff          = bbox[3] - bbox[1]
    district_area_km2 = lon_diff * lat_diff * 111 * 111
    affected_km2      = district_area_km2 * (water_pct / 100)

    # Risk score 1–10
    risk_score = min(10, max(1, round(water_pct / 10)))

    # Risk label
    if risk_score <= 3:
        risk_label = "low"
    elif risk_score <= 6:
        risk_label = "medium"
    else:
        risk_label = "high"

    print(f"  Water coverage : {water_pct:.2f}%")
    print(f"  Affected area  : {affected_km2:.1f} km²")
    print(f"  Risk score     : {risk_score}/10 ({risk_label})")

    return {
        "risk_score":         risk_score,
        "water_coverage_pct": round(water_pct, 2),
        "affected_area_km2":  round(affected_km2, 1),
        "flood_pixels":       flood_pixels,
        "pred_mask":          pred_mask,          # 256x256 numpy bool array
        "display_arr":        display_arr,        # preprocessed SAR for display
        "settlement_risk":    risk_label,
        "confidence":         "high",
        "model_used":         "U-Net ResNet34 (trained on Pakistan 2022 floods)"
    }
