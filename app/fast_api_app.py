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

import os

import google.auth
from fastapi import FastAPI
from google.adk.cli.fast_api import get_fast_api_app
from google.cloud import logging as google_cloud_logging
from vertexai import agent_engines

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

setup_telemetry()
_, project_id = google.auth.default()
logging_client = google_cloud_logging.Client()
logger = logging_client.logger(__name__)
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Agent Runtime session configuration
# Check if we should use in-memory session for testing (set USE_IN_MEMORY_SESSION=true for E2E tests)
use_in_memory_session = os.environ.get("USE_IN_MEMORY_SESSION", "").lower() in (
    "true",
    "1",
    "yes",
)

if use_in_memory_session:
    # Use in-memory session for local testing
    session_service_uri = None
else:
    # Use environment variable for agent name, default to project name
    default_agent_name = "nyc-agent"
    agent_name = os.environ.get("AGENT_ENGINE_SESSION_NAME", default_agent_name)

    # Check if an agent with this name already exists
    existing_agents = list(agent_engines.list(filter=f"display_name={agent_name}"))

    if existing_agents:
        # Use the existing agent
        agent_runtime = existing_agents[0]
    else:
        # Create a new agent if none exists
        agent_runtime = agent_engines.create(display_name=agent_name)

    session_service_uri = f"agentengine://{agent_runtime.resource_name}"

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=True,
)
app.title = "nyc-agent"
app.description = "API for interacting with the Agent nyc-agent"


from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.background_ingest import run_ingestion
from app.app_utils.snapshot_store import get_latest_snapshot

@app.get("/latest_snapshot")
def read_latest_snapshot() -> dict:
    """Returns the most recent ingested Times Square vision snapshot from Firestore (~100ms)."""
    snapshot = get_latest_snapshot()
    if snapshot:
        return {"status": "success", "snapshot": snapshot}
    return {"status": "empty", "message": "No snapshot available"}


@app.post("/ingest")
def trigger_ingestion(cam_name: str = "tsrobo1") -> dict:
    """Triggers periodic camera ingestion (called every 5 min by Cloud Scheduler)."""
    try:
        snapshot = run_ingestion(cam_name=cam_name)
        return {"status": "success", "snapshot": snapshot}
    except Exception as e:
        logger.log_text(f"Ingestion failed: {e}", severity="ERROR")
        return {"status": "error", "message": str(e)}


static_dir = os.path.join(AGENT_DIR, "app", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/ui")
    @app.get("/chat")
    def serve_frontend():
        return FileResponse(os.path.join(static_dir, "index.html"))



# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)

