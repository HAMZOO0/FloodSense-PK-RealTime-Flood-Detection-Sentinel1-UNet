"""FloodSense-PK REST backend (FastAPI + MongoDB).

Serves the full flood-intelligence pipeline (GEE Sentinel-1 + U-Net, FFD river
flows, 2010 Landsat benchmark, agentic workflow, RAG chat) to the web and
mobile clients over HTTP.

Run with:
    uvicorn backend.app:app --host 0.0.0.0 --port 8000
"""
