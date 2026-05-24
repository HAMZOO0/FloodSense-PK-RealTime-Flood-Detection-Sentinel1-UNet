# 🌊 FloodSense
### AI-Powered Flood Early Warning System for Pakistan

> Built for GDG Hackathon 2025 — Social Impact / Disaster Response Track

---

## 📌 What is FloodSense?

FloodSense is a real-time flood detection and early warning system for Pakistan. It pulls live satellite imagery from **Google Earth Engine**, runs it through a custom-trained **U-Net ResNet34 deep learning model** (trained on the 2022 Pakistan floods), and produces district-level flood risk scores with pixel-accurate flood masks.

Pakistan loses **$3–4 billion** to floods every year. Millions in KPK and Sindh receive less than 6 hours of warning before displacement. FloodSense changes that.

---

## 🧠 How It Works

```
Google Earth Engine (Sentinel-1 SAR)
            ↓
    SAR satellite image
            ↓
  U-Net ResNet34 model        ← trained on 2022 Pakistan flood data
            ↓
  Pixel-level flood mask      ← 98.94% IoU accuracy
            ↓
  Risk score (1–10)
  Affected area (km²)
  Water coverage (%)
            ↓
  Visualization + JSON output
```

---

## 🛰️ Data Source

- **Satellite**: Sentinel-1 SAR (C-band radar) via Google Earth Engine
- **Why SAR**: Works through clouds and at night — critical during monsoon season
- **Coverage**: All major flood-risk districts in Pakistan
- **Training data**: 2022 Pakistan floods — one of the worst flood disasters in recorded history (33 million people affected)

---

## 🤖 Model

| Detail | Value |
|---|---|
| Architecture | U-Net with ResNet34 encoder |
| Training data | Sentinel-1 SAR — Pakistan 2022 floods |
| Total patches | 10,666 (128×128 px each) |
| Training epochs | 60 |
| Best Validation IoU | **0.9894** |
| Parameters | ~24M |
| Loss function | Dice Loss + Focal Loss |

---

## 🗺️ Supported Districts

| District | Province | Bounding Box |
|---|---|---|
| DG Khan | Punjab | 70.2°E – 71.2°E, 29.8°N – 30.8°N |
| Sukkur | Sindh | 68.5°E – 69.5°E, 27.5°N – 28.5°N |
| Nowshera | KPK | 71.8°E – 72.4°E, 34.0°N – 34.6°N |
| Larkana | Sindh | 67.8°E – 68.5°E, 27.3°N – 27.9°N |

---

## 🚀 Setup & Installation

### 1. Clone the repo
```bash
git clone https://github.com/yourname/floodsense.git
cd floodsense
```

### 2. Create virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux
```

### 3. Install dependencies
```bash
pip install earthengine-api segmentation-models-pytorch torch torchvision timm rasterio albumentations Pillow matplotlib numpy requests python-dotenv
```

### 4. Set up environment variables
Create a `.env` file in the root folder:
```
PROJECT_ID=your-google-cloud-project-id
GEMINI_API_KEY=your-gemini-api-key
```

### 5. Authenticate Google Earth Engine
```bash
earthengine authenticate
```

### 6. Add model weights
Place `best_model.pth` inside the `models/` folder:
```
floodsense/
└── models/
    └── best_model.pth    ← ~90MB, download from Kaggle
```

### 7. Run
```bash
python main.py
```

---

## 📁 Project Structure

```
floodsense/
├── main.py                  # main pipeline — GEE fetch → model → output
├── model_inference.py       # U-Net model loading and prediction
├── models/
│   └── best_model.pth       # trained model weights (~90MB)
├── .env                     # API keys (not committed to git)
├── .gitignore
└── README.md
```

---

## 📊 Output

For each district analysis you get:

- **Visualization** — 3-panel PNG: raw SAR image, flood mask overlay, risk score bar
- **JSON result** — structured output with all metrics

```json
{
  "district": "DG Khan",
  "date_range": "2022-08-15 to 2022-09-15",
  "risk_score": 8,
  "water_pct": 34.7,
  "area_km2": 412.3,
  "risk_level": "high"
}
```

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Satellite imagery | Google Earth Engine (Sentinel-1 SAR) |
| Deep learning | PyTorch + segmentation-models-pytorch |
| Model architecture | U-Net ResNet34 |
| Image processing | Pillow, NumPy, Albumentations |
| Visualization | Matplotlib |
| Environment | Python 3.10+ |

---

## 🌍 Why This Matters

| Metric | Value |
|---|---|
| Annual flood-affected population | 5–8 million |
| Economic loss per season | USD 3–4 billion |
| 2022 super-flood displaced | 33 million people |
| Average warning time (rural) | < 6 hours |
| Our model accuracy | 98.94% IoU |

---


> *"Pakistan loses billions to floods every year not because we lack satellites, or AI, or mobile phones — but because no one connected them. FloodSense connects them."*