"""FastAPI backend — serves dashboard data and KB query endpoint."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from reviewer import config
from reviewer.database import (
    get_all_features,
    get_all_lobs,
    get_all_reviews,
    get_dashboard_stats,
    get_feature_detail,
    init_db,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="PR Reviewer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
def dashboard():
    return get_dashboard_stats()


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

@app.get("/api/features")
def list_features():
    return get_all_features()


@app.get("/api/features/{feature_name}")
def feature_detail(feature_name: str):
    detail = get_feature_detail(feature_name)
    if not detail:
        raise HTTPException(status_code=404, detail=f"Feature '{feature_name}' not found")
    return detail


# ---------------------------------------------------------------------------
# LOBs
# ---------------------------------------------------------------------------

@app.get("/api/lobs")
def list_lobs():
    return get_all_lobs()


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@app.get("/api/reviews")
def list_reviews(limit: int = Query(default=50, le=200)):
    return get_all_reviews(limit=limit)


# ---------------------------------------------------------------------------
# KB Query
# ---------------------------------------------------------------------------

class KBQueryRequest(BaseModel):
    question: str
    use_live: bool = True


class KBQueryResponse(BaseModel):
    answer: str


@app.post("/api/kb/query", response_model=KBQueryResponse)
def kb_query(req: KBQueryRequest):
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    from reviewer.kb_query import ask
    try:
        answer = ask(req.question, registry_path=config.REGISTRY_PATH, use_live=req.use_live)
        return KBQueryResponse(answer=answer)
    except Exception as e:
        logger.exception("KB query failed")
        raise HTTPException(status_code=500, detail=str(e))
