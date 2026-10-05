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

from unittest.mock import MagicMock, patch
from app.app_utils.snapshot_store import TimesSquareSnapshot, save_snapshot, get_latest_snapshot, get_snapshots_in_window
from app.background_ingest import run_ingestion


def test_snapshot_store_save_and_retrieve() -> None:
    snapshot = TimesSquareSnapshot(
        estimated_people_count=120,
        crowd_density="HIGH",
        traffic_activity="Heavy taxi traffic",
        weather_summary="Clear night",
        notable_sightings=["Broadway sign"],
        image_url="https://i.ibb.co/sample.jpg"
    )

    saved = save_snapshot(snapshot)
    assert saved is True

    latest = get_latest_snapshot()
    assert latest is not None
    assert latest["estimated_people_count"] == 120
    assert latest["crowd_density"] == "HIGH"
    assert latest["image_url"] == "https://i.ibb.co/sample.jpg"

    window = get_snapshots_in_window(minutes_back=60)
    assert len(window) >= 1
    assert window[0]["estimated_people_count"] == 120


@patch("app.background_ingest.get_all_earthcam_frames")
@patch("google.genai.Client")
def test_run_ingestion(mock_genai_client: MagicMock, mock_get_all_frames: MagicMock) -> None:
    from google.genai import types

    mock_part1 = types.Part.from_bytes(data=b"fake", mime_type="image/jpeg")
    mock_get_all_frames.return_value = {
        "tsnorth4k": {
            "image_part": mock_part1,
            "image_url": "https://i.ibb.co/test_north.jpg",
            "image_bytes": b"fake",
        },
        "tsrobo1": {
            "image_part": mock_part1,
            "image_url": "https://i.ibb.co/test_robo1.jpg",
            "image_bytes": b"fake",
        }
    }

    mock_client_instance = MagicMock()
    mock_genai_client.return_value = mock_client_instance

    mock_parsed_snapshot = TimesSquareSnapshot(
        estimated_people_count=85,
        crowd_density="MEDIUM",
        traffic_activity="Normal vehicle flow",
        weather_summary="Partly cloudy",
        notable_sightings=["Samsung billboard"],
        image_url="https://i.ibb.co/test_north.jpg",
        camera_urls={
            "tsnorth4k": "https://i.ibb.co/test_north.jpg",
            "tsrobo1": "https://i.ibb.co/test_robo1.jpg",
        }
    )

    mock_response = MagicMock()
    mock_response.parsed = mock_parsed_snapshot
    mock_client_instance.models.generate_content.return_value = mock_response

    result = run_ingestion("all")
    assert result["estimated_people_count"] == 85
    assert result["crowd_density"] == "MEDIUM"
    assert result["image_url"] == "https://i.ibb.co/test_north.jpg"
    assert "tsnorth4k" in result["camera_urls"]

