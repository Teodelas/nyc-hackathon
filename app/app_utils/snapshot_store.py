# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TimesSquareSnapshot(BaseModel):
    """Structured vision record captured every 5 minutes from NYC Times Square across 4 camera feeds."""

    timestamp: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of snapshot",
    )
    estimated_people_count: int = Field(
        ..., description="Estimated total number of visible people across all camera frames"
    )
    crowd_density: str = Field(
        ..., description="Density classification: LOW, MEDIUM, HIGH, or OVERCROWDED"
    )
    traffic_activity: str = Field(
        ..., description="Brief description of vehicle traffic on streets across all views"
    )
    weather_summary: str = Field(
        ..., description="Weather or ambient lighting summary (e.g., Clear, Rain, Night lights)"
    )
    notable_sightings: List[str] = Field(
        default_factory=list,
        description="List of notable visual sightings, events, or billboards",
    )
    image_url: str = Field(
        default="", description="Primary/fallback public verification image URL"
    )
    camera_urls: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of camera ID (tsnorth4k, tsrobo3, tsstreet, tsrobo1) to public GCS V4 signed URL",
    )



# Local fallback storage in memory / local JSON file when Firestore is unavailable
_LOCAL_SNAPSHOTS: List[dict] = []
_LOCAL_STORE_PATH = os.path.join(os.path.dirname(__file__), "snapshots_local.json")


def _get_firestore_client() -> Optional[Any]:
    """Attempts to initialize and return a Google Cloud Firestore client."""
    try:
        from google.cloud import firestore

        project_id = os.environ.get("GCP_PROJECT", os.environ.get("GOOGLE_CLOUD_PROJECT", "secure-agents-501013"))
        db = firestore.Client(project=project_id)
        return db
    except Exception as e:
        logger.debug("Firestore client unavailable, using local store: %s", e)
        return None


def save_snapshot(snapshot: TimesSquareSnapshot) -> bool:
    """Saves a TimesSquareSnapshot to Firestore (or local fallback)."""
    data = snapshot.model_dump()
    db = _get_firestore_client()
    if db:
        try:
            # Document ID keyed by timestamp string for easy ordering
            doc_id = snapshot.timestamp.replace(":", "-").replace(".", "-")
            db.collection("times_square_snapshots").document(doc_id).set(data)
            logger.info("Successfully saved snapshot %s to Firestore", doc_id)
            return True
        except Exception as e:
            logger.warning("Failed to write snapshot to Firestore, using local store: %s", e)

    # Local fallback
    global _LOCAL_SNAPSHOTS
    _load_local_store()
    _LOCAL_SNAPSHOTS.append(data)
    try:
        with open(_LOCAL_STORE_PATH, "w") as f:
            json.dump(_LOCAL_SNAPSHOTS, f, indent=2)
    except Exception as e:
        logger.warning("Failed to write to local snapshot file: %s", e)
    return True


def get_latest_snapshot() -> Optional[dict]:
    """Retrieves the most recent snapshot."""
    db = _get_firestore_client()
    if db:
        try:
            docs = (
                db.collection("times_square_snapshots")
                .order_by("timestamp", direction="DESCENDING")
                .limit(1)
                .get()
            )
            for doc in docs:
                return doc.to_dict()
        except Exception as e:
            logger.warning("Firestore read latest failed, using local store: %s", e)

    # Local store fallback
    _load_local_store()
    if _LOCAL_SNAPSHOTS:
        return _LOCAL_SNAPSHOTS[-1]
    return None


def get_snapshots_in_window(minutes_back: int = 1440) -> List[dict]:
    """Retrieves all snapshots captured within the last N minutes (or all history if minutes_back <= 0)."""
    cutoff_time = None
    if minutes_back > 0:
        cutoff_time = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=minutes_back)
        ).isoformat()

    db = _get_firestore_client()
    if db:
        try:
            query = db.collection("times_square_snapshots")
            if cutoff_time:
                query = query.where("timestamp", ">=", cutoff_time)
            docs = query.order_by("timestamp", direction="DESCENDING").get()
            results = [doc.to_dict() for doc in docs]
            if results:
                return results
        except Exception as e:
            logger.warning("Firestore query window failed, using local store: %s", e)

    # Local store fallback
    _load_local_store()
    if cutoff_time:
        results = [s for s in _LOCAL_SNAPSHOTS if s.get("timestamp", "") >= cutoff_time]
    else:
        results = list(_LOCAL_SNAPSHOTS)
    results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return results



def _load_local_store() -> None:
    global _LOCAL_SNAPSHOTS
    if not _LOCAL_SNAPSHOTS and os.path.exists(_LOCAL_STORE_PATH):
        try:
            with open(_LOCAL_STORE_PATH, "r") as f:
                _LOCAL_SNAPSHOTS = json.load(f)
        except Exception as e:
            logger.warning("Could not load local snapshot file: %s", e)
