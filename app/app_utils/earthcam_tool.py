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

import base64
import logging
import os
from typing import Any

import numpy as np
import requests
from google.genai import types

logger = logging.getLogger(__name__)


import datetime
import google.auth
from google.auth.impersonated_credentials import Credentials as ImpersonatedCredentials
from google.cloud import storage


def _upload_to_gcs(image_bytes: bytes) -> str | None:
    """Uploads JPEG image bytes to private GCS bucket and generates a V4 GET Signed URL for the frontend UI."""
    bucket_name = os.environ.get("GCS_FRAME_BUCKET", "nyc-agent-camera-frames-501013")
    try:
        base_credentials, project_id = google.auth.default()
        sa_email = os.environ.get("GCS_SIGNING_SERVICE_ACCOUNT", "615155805710-compute@developer.gserviceaccount.com")

        # Create signing credentials using IAM signBlob API via impersonated credentials
        signing_credentials = ImpersonatedCredentials(
            source_credentials=base_credentials,
            target_principal=sa_email,
            target_scopes=["https://www.googleapis.com/auth/devstorage.read_only"],
        )

        client = storage.Client(project=project_id, credentials=base_credentials)
        bucket = client.bucket(bucket_name)

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        blob_name = f"snapshots/{now_str}.jpg"
        blob = bucket.blob(blob_name)

        blob.upload_from_string(image_bytes, content_type="image/jpeg")

        # Generate V4 Signed URL valid for 2 hours for frontend rendering using IAM signBlob
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=2),
            method="GET",
            credentials=signing_credentials,
        )
        logger.info("Successfully uploaded EarthCam frame to GCS: gs://%s/%s (V4 Signed URL generated)", bucket_name, blob_name)
        return signed_url
    except Exception as e:
        logger.warning("GCS upload or signing failed, falling back to ImgBB: %s", e)
        return _upload_to_imgbb(image_bytes)



def _upload_to_imgbb(image_bytes: bytes) -> str | None:
    """Uploads JPEG image bytes to ImgBB (fallback upload if key configured)."""
    api_key = os.environ.get("IMGBB_API_KEY")
    if not api_key:
        logger.warning("IMGBB_API_KEY not configured in environment; skipping fallback upload.")
        return None
    try:
        b64_img = base64.b64encode(image_bytes).decode("utf-8")
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        res = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": api_key, "image": b64_img, "expiration": 86400},
            headers=headers,
            timeout=10,
        )
        if res.status_code == 200:
            data = res.json()
            image_url = data.get("data", {}).get("url")
            logger.info("Successfully uploaded EarthCam frame to ImgBB fallback: %s", image_url)
            return image_url
    except Exception as e:
        logger.warning("Fallback ImgBB upload failed: %s", e)
    return None



EARTHCAM_CAMERAS = ["tsnorth4k", "tsrobo3", "tsstreet", "tsrobo1"]


def capture_single_cam(cam_name: str) -> dict:
    """Captures a single camera frame from EarthCam, resizes it, and uploads to GCS."""
    import time
    import cv2
    import streamlink

    session = streamlink.Streamlink()
    session.set_option(
        "http-headers",
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.earthcam.com/",
        },
    )

    url = f"https://www.earthcam.com/usa/newyork/timessquare/?cam={cam_name}"

    for attempt in range(1, 4):
        try:
            streams = session.streams(url)
            if not streams:
                logger.warning("Attempt %d: No streams found for camera %s", attempt, cam_name)
                time.sleep(0.5)
                continue
            stream = streams.get("best") or streams.get("worst")
            cap = cv2.VideoCapture(stream.url)
            ret, frame = False, None
            # Read up to 15 frames to pass initial HLS buffering / black keyframe
            for _ in range(15):
                r, f = cap.read()
                if r and f is not None:
                    ret, frame = r, f
                    if f.mean() > 8.0:  # Skip pure black buffering frames
                        break
            cap.release()

            if not ret or frame is None:
                logger.warning("Attempt %d: Failed to read valid frame for camera %s", attempt, cam_name)
                time.sleep(0.5)
                continue

            if isinstance(frame, np.ndarray) and len(frame.shape) >= 2:
                h, w = frame.shape[:2]
                max_dim = 1024
                if max(h, w) > max_dim:
                    scale = max_dim / float(max(h, w))
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
            success, buffer = cv2.imencode(".jpg", frame, encode_param)
            if not success:
                time.sleep(0.5)
                continue

            image_bytes = buffer.tobytes()
            image_url = _upload_to_gcs(image_bytes) or ""

            return {
                "cam_name": cam_name,
                "image_bytes": image_bytes,
                "image_url": image_url,
                "image_part": types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            }
        except Exception as e:
            logger.error("Attempt %d error capturing camera frame for %s: %s", attempt, cam_name, e)
            time.sleep(0.5)

    return {}


from concurrent.futures import ThreadPoolExecutor


def get_all_earthcam_frames() -> dict:
    """Captures frames across all 4 EarthCam Times Square cameras concurrently."""
    results = {}
    with ThreadPoolExecutor(max_workers=len(EARTHCAM_CAMERAS)) as executor:
        future_to_cam = {executor.submit(capture_single_cam, cam): cam for cam in EARTHCAM_CAMERAS}
        for future in future_to_cam:
            cam = future_to_cam[future]
            try:
                cam_data = future.result(timeout=15)
                if cam_data:
                    results[cam] = cam_data
            except Exception as e:
                logger.error("Error capturing camera frame for %s concurrently: %s", cam, e)
    return results


def get_earthcam_frame(cam_name: str = "tsrobo1") -> Any:
    """Captures live image frame(s) from NYC Times Square EarthCam feeds.

    If cam_name is 'all', captures frames across all 4 cameras (tsnorth4k, tsrobo3, tsstreet, tsrobo1).

    Args:
        cam_name: The EarthCam camera identifier (e.g. 'tsnorth4k', 'tsrobo3', 'tsstreet', 'tsrobo1', or 'all').
    """
    if cam_name == "all":
        all_frames = get_all_earthcam_frames()
        parts = []
        info_lines = ["Captured live multi-camera frames from 4 Times Square cameras:"]
        for cam, data in all_frames.items():
            parts.append(data["image_part"])
            info_lines.append(f"- Camera '{cam}': Verification URL: {data.get('image_url', '')}")
        parts.append(types.Part.from_text(text="\n".join(info_lines)))
        return parts

    cam_data = capture_single_cam(cam_name)
    if not cam_data:
        raise ValueError(f"Could not capture frame for camera '{cam_name}'")

    image_url_text = (
        f"Captured live Times Square webcam frame from camera '{cam_name}'. "
        f"Public verification image URL: {cam_data.get('image_url') or 'Upload unavailable'}"
    )

    return [
        cam_data["image_part"],
        types.Part.from_text(text=image_url_text),
    ]



def get_latest_snapshot_tool() -> dict:
    """Retrieves the most recent 5-minute pre-extracted Times Square vision snapshot from memory/database.

    Returns:
        A dictionary with crowd count, density, weather, traffic, notable events, and image_url.
    """
    from app.app_utils.snapshot_store import get_latest_snapshot

    snapshot = get_latest_snapshot()
    if snapshot:
        return snapshot
    return {
        "status": "No pre-extracted periodic snapshot found yet. Live capture recommended.",
        "note": "Call get_earthcam_frame() to capture a real-time frame.",
    }


def get_historical_snapshots_tool(minutes_back: int = 1440) -> dict:
    """Retrieves pre-extracted 5-minute Times Square vision snapshots captured within the last N minutes.

    Supports ANY requested historical time window (e.g., 60 for 1h, 1440 for 24h, 10080 for 7d, 0 for all time).

    Args:
        minutes_back: How many minutes into the past to retrieve (default: 1440 minutes = 24 hours).
                      Set to 0 to retrieve all available historical snapshots.

    Returns:
        A dictionary containing the list of structured snapshot records under 'snapshots' and total 'count'.
    """
    from app.app_utils.snapshot_store import get_snapshots_in_window

    snapshots = get_snapshots_in_window(minutes_back=minutes_back)
    if snapshots:
        return {"status": "success", "count": len(snapshots), "snapshots": snapshots}
    return {
        "status": f"No historical snapshots found in the last {minutes_back} minutes.",
        "note": "Calling get_latest_snapshot_tool() or get_earthcam_frame().",
        "count": 0,
        "snapshots": [],
    }



