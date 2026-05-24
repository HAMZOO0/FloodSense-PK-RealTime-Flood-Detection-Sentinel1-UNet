import os
import torch
import numpy as np
from PIL import Image
import io
import albumentations as A
from albumentations.pytorch import ToTensorV2
import segmentation_models_pytorch as smp

# ── Load your trained model ──────────────────────────────
def load_flood_model(weights_path="models/best_model.pth"):
    if not os.path.isabs(weights_path):
        weights_path = os.path.join(os.path.dirname(__file__), weights_path)

    if not os.path.exists(weights_path):
        raise FileNotFoundError(f"Model weights not found: {weights_path}")

    model = smp.Unet(
        encoder_name="resnet34",
        encoder_weights=None,      # don't download imagenet, we have our weights
        in_channels=3,
        classes=1,
        activation=None
    )
    model.load_state_dict(
        torch.load(weights_path, map_location="cpu", weights_only=False)
    )
    model.eval()
    print(f"✅ Flood model loaded from {weights_path}")
    return model


# ── Preprocess SAR image bytes → tensor ──────────────────
def preprocess_image(image_bytes):
    """
    Takes raw PNG bytes from GEE.
    Returns tensor ready for model input.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
    img = img.resize((256, 256))
    arr = np.array(img, dtype=np.float32)

    # Same normalization as training
    # Training mapped: land(1)→0.0, flood(2)→1.0
    # For raw SAR: normalize to 0-1 range
    arr = arr / 255.0

    # Repeat to 3 channels (model expects RGB-like input)
    arr = np.stack([arr, arr, arr], axis=-1)

    transform = A.Compose([
        A.Normalize(
            mean=(0.485, 0.456, 0.406),
            std=(0.229, 0.224, 0.225)
        ),
        ToTensorV2()
    ])

    transformed = transform(image=arr)
    tensor = transformed["image"].unsqueeze(0)  # add batch dim
    return tensor


# ── Run flood segmentation ────────────────────────────────
def predict_flood(model, image_bytes, district_name, bbox):
    """
    Runs your U-Net on the SAR tile.
    Returns full analysis dict — same shape as Gemini used to return.
    """
    tensor = preprocess_image(image_bytes)

    with torch.no_grad():
        output = torch.sigmoid(model(tensor))

    pred_mask = (output.cpu().numpy()[0, 0] > 0.5)  # binary flood mask

    # ── Calculate stats from mask ─────────────────────────
    total_pixels = pred_mask.size
    flood_pixels = int(pred_mask.sum())
    water_pct    = (flood_pixels / total_pixels) * 100

    # Estimate km2 from bbox
    lon_diff = bbox[2] - bbox[0]
    lat_diff = bbox[3] - bbox[1]
    district_area_km2 = lon_diff * lat_diff * 111 * 111  # rough conversion
    affected_km2 = district_area_km2 * (water_pct / 100)

    # Risk score
    risk_score = min(10, max(1, round(water_pct / 8) + 1))

    # Risk level label
    if risk_score <= 3:
        settlement_risk = "low"
    elif risk_score <= 6:
        settlement_risk = "medium"
    else:
        settlement_risk = "high"

    return {
        "risk_score":         risk_score,
        "water_coverage_pct": round(water_pct, 2),
        "affected_area_km2":  round(affected_km2, 1),
        "flood_pixels":       flood_pixels,
        "pred_mask":          pred_mask,        # numpy array for visualization
        "settlement_risk":    settlement_risk,
        "confidence":         "high",           # model IoU = 0.9894
        "model_used":         "U-Net ResNet34 (trained on Pakistan 2022 floods)"
    }