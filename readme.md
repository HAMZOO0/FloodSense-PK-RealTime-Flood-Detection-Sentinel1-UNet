# FloodSense-PK
AI-powered flood early warning dashboard for Pakistan

![Architecture](docs/architecture.png)

## What it does
FloodSense estimates **district-level flood risk** by combining:
- **Live Sentinel-1 SAR (GEE)** + **UNet ResNet34** → current flood % and mask
- **Historical 2010 flood baseline (GEE Landsat)** → 2010 new flood % for comparison
- **FFC river discharge scraper** → inflow/outflow + NORMAL/HIGH/EXTREME status
- **Groq AI** → strategic recommendations (fallback to simulated insights if keys are missing)

The main user interface is **Streamlit** (single non-overlapping dashboard).

![Streamlit UI](docs/streamlit_ui.png)

## Key outputs (in the Streamlit app)
- KPIs: Current flood %, 2010 new flood %, Δ vs 2010, risk score (1–10)
- One clear UNet diagram (SAR + probability + flood mask)
- Flood probability heatmap
- River-flow visualizations (status distribution, top inflow/outflow, inflow vs outflow scatter)
- Groq AI strategic insights

## Setup
### 1) Create your virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 2) Install dependencies
```powershell
pip install earthengine-api torch torchvision timm rasterio segmentation-models-pytorch albumentations Pillow matplotlib numpy requests python-dotenv streamlit geopandas shapely beautifulsoup4
```

### 3) Configure environment variables (`.env`)
Create a file `.env` in the repo root:
```env
PROJECT_ID=your-google-cloud-project-id
GROQ_API_KEY=gsk_...
Data_URL=https://...  # FFC discharge page URL
# Optional:
GEMINI_API_KEY=your-gemini-api-key
```

### 4) Authenticate Google Earth Engine
```powershell
earthengine authenticate
```

## Run (recommended: Streamlit)
```powershell
streamlit run streamlit_app.py
```

Usage in the app:
1. Choose a **District**
2. Choose **Current SAR start date** and **Current SAR end date**
3. Click **Run analysis**
4. Review tabs: **Overview**, **Detection**, **River Flows**, **AI Insights**

## Optional: Run batch pipeline (generates a PNG only)
```powershell
python main.py --quick --skip-historical
```

You can also set a custom SAR window:
```powershell
python main.py --skip-historical --current-start 2024-01-01 --current-end 2024-01-31
```

Batch run writes:
- `outputs/flood_map.png`
- `data/json/river_flows.json`
- `data/json/ai_insights.json`

## Project structure
- `streamlit_app.py` : main UI (single dashboard)
- `main.py` : optional batch pipeline
- `models/model_inference.py` : UNet preprocessing + prediction
- `engine/ai_alerts.py` : Groq AI insight generation + fallback
- `scrapers/ffc_scraper.py` : FFC river discharge scraping
- `utils/ndwi.py` : GEE Landsat NDWI (2010 historical mask)
- `utils/districts.py` : district name detection + flood % calculation

## Notes / performance
- Computing the **2010 Landsat mask** can take a while. In Streamlit, it’s cached in your session (so it won’t repeat every click).
- UNet inference runs after the SAR thumbnail is fetched from GEE.

## Technical Deep Dive

### 1. The UNet Model: Full Image Flow
The lifecycle of a single flood detection prediction follows these steps:
1.  **Request (GEE):** When a district and date are selected, the system fetches **Sentinel-1 SAR** imagery (VV band) via Google Earth Engine.
2.  **Data Form:** Data arrives as **GeoTIFF** bytes (matrix of radar backscatter values in dB).
3.  **Preprocessing:**
    *   **Normalization:** Raw dB values (approx. -25 to 0) are scaled to [0, 1].
    *   **Synthetic RGB:** Creates a 3-channel tensor: Channel 1 (VV), Channel 2 (VH approx), Channel 3 (VH/VV ratio).
    *   **Resizing:** Imagery is standardized to **256x256 pixels**.
4.  **Inference:** The tensor is fed into a **UNet (ResNet34)** model trained on Pakistan-specific flood events.
5.  **Output:** A probability map is generated. Pixels > 0.5 are classified as **Flood** (blue overlay).

### 2. FFC (Federal Flood Commission) Data
1.  **Source:** Official FFC discharge web portal.
2.  **Scraping & Parsing:** Uses `BeautifulSoup` to extract real-time table data for major barrages (Tarbela, Sukkur, Kotri, etc.).
3.  **Metrics:** Tracks **Inflow**, **Outflow**, and **Risk Status** (NORMAL, HIGH, EXTREME).
4.  **Visualization:** Data is parsed into JSON and rendered as interactive charts in the "River Flows" tab.

### 3. 2010 Historical Baseline
1.  **Satellite Source:** **Landsat 5** imagery (Collection 2 Level 2) via GEE.
2.  **Methodology (MNDWI):** Uses the Modified Normalized Difference Water Index:
    $$\text{MNDWI} = \frac{\text{Green} - \text{SWIR1}}{\text{Green} + \text{SWIR1}}$$
3.  **Temporal Analysis:**
    *   **Baseline:** 2009 median composite (permanent water bodies).
    *   **Flood Peak:** July–September 2010 maximum composite.
4.  **Result:** The system subtracts the 2009 baseline from the 2010 peak to isolate **"New Flooded Areas"** for severity benchmarking.

## License
Add your license here.