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

import pytest
from google.genai import types

from app.app_utils.earthcam_tool import get_earthcam_frame


@patch("app.app_utils.earthcam_tool._upload_to_gcs")
@patch("streamlink.Streamlink")
@patch("cv2.VideoCapture")
@patch("cv2.imencode")
def test_get_earthcam_frame_success(
    mock_imencode: MagicMock,
    mock_video_capture: MagicMock,
    mock_streamlink_class: MagicMock,
    mock_upload: MagicMock,
) -> None:
    """Test successful capture of an EarthCam webcam frame."""
    mock_session = MagicMock()
    mock_streamlink_class.return_value = mock_session

    mock_stream = MagicMock()
    mock_stream.url = "https://example.com/live.m3u8"
    mock_session.streams.return_value = {"best": mock_stream}

    import numpy as np

    mock_cap = MagicMock()
    mock_video_capture.return_value = mock_cap
    mock_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, mock_frame)

    mock_imencode.return_value = (True, MagicMock(tobytes=lambda: b"fake_jpeg_bytes"))
    mock_upload.return_value = "https://storage.googleapis.com/nyc-agent-camera-frames-501013/snapshots/test.jpg?X-Goog-Algorithm=GOOG4-RSA-SHA256"

    result = get_earthcam_frame(cam_name="tsrobo1")

    assert isinstance(result, list)
    assert len(result) == 2
    assert isinstance(result[0], types.Part)
    assert result[0].inline_data is not None
    assert result[0].inline_data.mime_type == "image/jpeg"
    assert result[0].inline_data.data == b"fake_jpeg_bytes"
    assert isinstance(result[1], types.Part)
    assert "https://storage.googleapis.com" in result[1].text



@patch("streamlink.Streamlink")
def test_get_earthcam_frame_no_streams(mock_streamlink_class: MagicMock) -> None:
    """Test error handling when no streams are found."""
    mock_session = MagicMock()
    mock_streamlink_class.return_value = mock_session
    mock_session.streams.return_value = {}

    with pytest.raises(ValueError, match="Could not capture frame"):
        get_earthcam_frame(cam_name="nonexistent_cam")

