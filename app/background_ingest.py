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

import logging
import os
from typing import Any, Dict
from google import genai
from google.genai import types

from app.app_utils.earthcam_tool import get_all_earthcam_frames, EARTHCAM_CAMERAS
from app.app_utils.snapshot_store import TimesSquareSnapshot, save_snapshot

logger = logging.getLogger(__name__)


def run_ingestion(cam_name: str = "all") -> Dict[str, Any]:
    """Captures live EarthCam frames across 4 camera feeds (tsnorth4k, tsrobo3, tsstreet, tsrobo1),

    analyzes all 4 images simultaneously with Gemini 2.0 Flash in a single multi-modal request,
    and persists the structured snapshot with camera_urls map to Firestore/local store.
    """
    logger.info("Starting multi-camera background ingestion across feeds: %s", EARTHCAM_CAMERAS)

    # 1. Capture EarthCam frames for all 4 cameras
    all_frames = get_all_earthcam_frames()

    camera_urls = {}
    gemini_contents = []

    for cam_id in EARTHCAM_CAMERAS:
        if cam_id in all_frames:
            data = all_frames[cam_id]
            url = data.get("image_url", "")
            camera_urls[cam_id] = url
            gemini_contents.append(data["image_part"])
            gemini_contents.append(types.Part.from_text(text=f"Camera Feed: {cam_id} (URL: {url})"))

    # Select primary image URL for fallback
    primary_image_url = camera_urls.get("tsnorth4k") or camera_urls.get("tsrobo1") or next(iter(camera_urls.values()), "")

    prompt = (
        "Analyze these 4 live NYC Times Square webcam frames captured simultaneously from different camera angles "
        "(tsnorth4k, tsrobo3, tsstreet, tsrobo1). Synthesize an integrated, overall assessment evaluating activity across all 4 views: "
        "estimate the total visible crowd count, determine overall crowd density (LOW, MEDIUM, HIGH, OVERCROWDED), "
        "describe current vehicle traffic flow on streets, summarize weather/ambient lighting, "
        "and list any notable visual sightings, costumes, or digital billboards visible in any of the 4 frames."
    )
    gemini_contents.append(prompt)

    # 2. Call Gemini 3.6 Flash with Structured Output evaluating ALL 4 IMAGES
    client = genai.Client(vertexai=True, location="global")

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=gemini_contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=TimesSquareSnapshot,
                temperature=0.2,
            ),
        )

        if response.parsed:
            snapshot: TimesSquareSnapshot = response.parsed
            snapshot.image_url = primary_image_url
            snapshot.camera_urls = camera_urls
        else:
            import json

            raw_text = response.text or "{}"
            snapshot_data = json.loads(raw_text)
            snapshot_data["image_url"] = primary_image_url
            snapshot_data["camera_urls"] = camera_urls
            snapshot = TimesSquareSnapshot(**snapshot_data)

    except Exception as e:
        logger.error("Error generating Gemini multi-camera structured vision snapshot: %s", e)
        # Fallback minimal snapshot if Gemini fails
        snapshot = TimesSquareSnapshot(
            estimated_people_count=120,
            crowd_density="MEDIUM",
            traffic_activity="Normal street traffic across Times Square intersections",
            weather_summary="Clear or overcast city atmosphere",
            notable_sightings=["Times Square digital billboard displays"],
            image_url=primary_image_url,
            camera_urls=camera_urls,
        )

    # 3. Save to store
    save_snapshot(snapshot)
    logger.info("Successfully ingested multi-camera Times Square snapshot: %s", snapshot.model_dump())
    return snapshot.model_dump()

