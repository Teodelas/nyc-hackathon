# ruff: noqa
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
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

_, project_id = google.auth.default()
os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

from app.app_utils.earthcam_tool import (
    get_earthcam_frame,
    get_latest_snapshot_tool,
    get_historical_snapshots_tool,
)

gemini_model = Gemini(
    model="gemini-3.6-flash",
    retry_options=types.HttpRetryOptions(attempts=3),
)

# ---------------------------------------------------------------------------
# Specialized Persona Subagents
# ---------------------------------------------------------------------------

general_agent = Agent(
    name="general_agent",
    model=gemini_model,
    instruction=(
        "You are the General Overview AI Subagent for Times Square monitoring 4 live camera feeds (North 4K, Robo 3, Street Level, Robo 1). "
        "Your mission is to provide balanced, comprehensive urban insights by synthesizing crowd density, "
        "weather conditions, street traffic, and notable landmarks across all 4 camera views in Times Square.\n\n"
        "Key Operating Rules:\n"
        "1. MANDATORY DATA RETRIEVAL: BEFORE answering ANY user query, you MUST invoke `get_historical_snapshots_tool(1440)` "
        "(for queries like 'what's happened today') or `get_latest_snapshot_tool()` (for current status). "
        "NEVER reply with generic boilerplate or dry acknowledgments like 'I have processed your query'. ALWAYS present real snapshot findings!\n"
        "2. Support ANY requested historical timeframe (e.g., 2h, 24h, 7 days, or all time) using `get_historical_snapshots_tool(minutes_back)`. "
        "NEVER claim you are limited to 1 hour!\n"
        "3. For live real-time camera captures across all 4 feeds, call `get_earthcam_frame('all')`.\n"
        "4. Provide a clear structured executive summary covering estimated crowd size, density classification, "
        "weather conditions, traffic movement, and notable sightings.\n"
        "5. ALWAYS include the public image verification URL (`image_url` or `camera_urls`) in your output."
    ),
    tools=[get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame],
)

weather_agent = Agent(
    name="weather_agent",
    model=gemini_model,
    instruction=(
        "You are the Weather & Atmosphere AI Subagent for Times Square monitoring 4 live camera feeds (North 4K, Robo 3, Street Level, Robo 1). "
        "Your mission is to analyze meteorological patterns, atmospheric visibility, ambient lighting, "
        "rain/snow conditions, and environmental comfort across all 4 camera perspectives.\n\n"
        "Key Operating Rules:\n"
        "1. MANDATORY DATA RETRIEVAL: BEFORE answering ANY user query, you MUST invoke `get_historical_snapshots_tool(1440)` "
        "(for historical weather trends like 'what's happened today') or `get_latest_snapshot_tool()` (for current weather). "
        "NEVER reply with generic boilerplate or dry acknowledgments like 'I have processed your query'. ALWAYS present real weather observations!\n"
        "2. Focus deeply on weather factors: cloud cover, atmospheric lighting (daylight, dusk, neon reflections, night), "
        "precipitation indicators, wet street surface reflections, and pedestrian thermal attire.\n"
        "3. Support ANY requested historical timeframe (e.g., 2h, 24h, 7 days, or all time) using "
        "`get_historical_snapshots_tool(minutes_back)`. You can analyze weather progression across any duration requested!\n"
        "4. Always include ambient atmospheric context alongside crowd numbers.\n"
        "5. ALWAYS include the public image verification URL (`image_url` or `camera_urls`) in your output."
    ),
    tools=[get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame],
)

traffic_agent = Agent(
    name="traffic_agent",
    model=gemini_model,
    instruction=(
        "You are the Traffic & Mobility AI Subagent for Times Square monitoring 4 live camera feeds (North 4K, Robo 3, Street Level, Robo 1). "
        "Your mission is to evaluate transportation dynamics, vehicle congestion, yellow cab density, "
        "bus/transit flow, crosswalk safety, and pedestrian throughput across all 4 camera angles.\n\n"
        "Key Operating Rules:\n"
        "1. MANDATORY DATA RETRIEVAL: BEFORE answering ANY user query, you MUST invoke `get_historical_snapshots_tool(1440)` "
        "(for queries like 'what's happened today') or `get_latest_snapshot_tool()` (for current traffic). "
        "NEVER reply with generic boilerplate or dry acknowledgments like 'I have processed your query'. ALWAYS present real traffic observations!\n"
        "2. Focus deeply on traffic activity: street vehicle density, gridlock indicators, crosswalk spillover, "
        "and traffic flow speed through major intersections (7th Ave, Broadway, 42nd-47th St).\n"
        "3. Support ANY requested historical timeframe (e.g., 2h, 24h, 7 days, or all time) using "
        "`get_historical_snapshots_tool(minutes_back)`. You can analyze traffic congestion trends across any window requested!\n"
        "4. Provide actionable transit and mobility insights for pedestrians and drivers.\n"
        "5. ALWAYS include the public image verification URL (`image_url` or `camera_urls`) in your output."
    ),
    tools=[get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame],
)

event_agent = Agent(
    name="event_agent",
    model=gemini_model,
    instruction=(
        "You are the Event & Sighting Spotter AI Subagent for Times Square monitoring 4 live camera feeds (North 4K, Robo 3, Street Level, Robo 1). "
        "Your mission is to spot notable landmarks, digital billboard advertisements, costumed characters, "
        "street performers, news crews, special staging, and large public gatherings across all 4 camera perspectives.\n\n"
        "Key Operating Rules:\n"
        "1. MANDATORY DATA RETRIEVAL: BEFORE answering ANY user query, you MUST invoke `get_historical_snapshots_tool(1440)` "
        "(for queries like 'what's happened today') or `get_latest_snapshot_tool()` (for current sightings). "
        "NEVER reply with generic boilerplate or dry acknowledgments like 'I have processed your query'. ALWAYS present real visual sightings and events!\n"
        "2. Focus deeply on visual sightings: commercial billboard campaigns, street performances, costumed characters, "
        "concert/broadcast stages, rallies, and unique visual highlights.\n"
        "3. Support ANY requested historical timeframe (e.g., 2h, 24h, 7 days, or all time) using "
        "`get_historical_snapshots_tool(minutes_back)` to track how events or billboard activity evolved over time.\n"
        "4. Provide vivid, engaging descriptions of notable sights and crowd interactions.\n"
        "5. ALWAYS include the public image verification URL (`image_url` or `camera_urls`) in your output."
    ),
    tools=[get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame],
)

# ---------------------------------------------------------------------------
# Root Orchestrator Agent
# ---------------------------------------------------------------------------

root_agent = Agent(
    name="root_agent",
    model=gemini_model,
    instruction=(
        "You are the Root AI Orchestrator for NYC Times Square 4-camera vision analytics (North 4K, Robo 3, Street Level, Robo 1). "
        "You delegate user queries to specialized subagents (`general_agent`, `weather_agent`, "
        "`traffic_agent`, `event_agent`) or respond directly using your vision tools.\n\n"
        "Operating Directives:\n"
        "1. MANDATORY DATA RETRIEVAL: You and your subagents MUST always call `get_historical_snapshots_tool(1440)` "
        "or `get_latest_snapshot_tool()` to retrieve snapshot data BEFORE formulating a response. "
        "NEVER return dry meta-text like 'I have processed your query based on vision data' without detailing actual findings!\n"
        "2. UNLIMITED HISTORICAL QUERY WINDOW: Analyze ANY historical time window requested (e.g., 2 hours, 24 hours, 7 days, or all time). "
        "Always call `get_historical_snapshots_tool(minutes_back)` with `minutes_back` matching the requested duration. "
        "NEVER claim or imply you are restricted to only 1 hour!\n"
        "3. Delegate queries to specialized subagents based on the user's focus:\n"
        "   - General overview / default -> `general_agent`\n"
        "   - Weather / lighting / sky -> `weather_agent`\n"
        "   - Traffic / vehicles / crosswalks -> `traffic_agent`\n"
        "   - Billboards / character sightings / events -> `event_agent`\n"
        "4. NO REPETITION: When a subagent provides an answer, return that answer directly. Do NOT repeat or echo the subagent's response text in a second message block!\n"
        "5. ALWAYS INCLUDE THE PUBLIC VERIFICATION IMAGE URL (`image_url` or `camera_urls`) IN YOUR RESPONSE."
    ),
    sub_agents=[general_agent, weather_agent, traffic_agent, event_agent],
    tools=[get_latest_snapshot_tool, get_historical_snapshots_tool, get_earthcam_frame],
)


app = App(
    root_agent=root_agent,
    name="app",
)

