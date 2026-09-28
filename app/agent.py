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

import datetime
import json
import os
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from .a2ui_utils import a2ui_callback

# Hardcoded project ID, Memory Bank ID, & Cloud Storage bucket name (crucial for Agent Platform compatibility)
FIRESTORE_PROJECT = "qwiklabs-gcp-02-ad44f2a2ea8f"
GCS_BUCKET_NAME = "travel-concierge-media-qwiklabs-gcp-02-ad44f2a2ea8f"
MEMORY_BANK_ID = "5715760619458658304"

# Initialize Firestore Client
db = firestore.Client(project=FIRESTORE_PROJECT)

# Load Agent Engine resource name from deployment_metadata.json if available
DEPLOYMENT_METADATA_PATH = Path(__file__).parent.parent / "deployment_metadata.json"
agent_engine_resource_name = None
if DEPLOYMENT_METADATA_PATH.exists():
    try:
        with open(DEPLOYMENT_METADATA_PATH, "r") as f:
            metadata = json.load(f)
            agent_engine_resource_name = metadata.get("remote_agent_runtime_id")
    except Exception:
        pass

code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=agent_engine_resource_name
)


# WRITE: after each turn, send the session to Memory Bank for extraction.
async def generate_memories_callback(callback_context: CallbackContext):
    try:
        await callback_context.add_session_to_memory()
    except ValueError:
        pass
    return None



def memory_bank_service_builder():
    return VertexAiMemoryBankService(
        project=FIRESTORE_PROJECT,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )



async def generate_destination_image(prompt: str, tool_context: ToolContext) -> str:
    """Generates a travel destination image using gemini-3.1-flash-lite-image in the global region, saves it as an artifact, uploads to GCS, and returns its public URL.

    Args:
        prompt: Detailed description of the travel scene, destination, or attraction to generate image for.

    Returns:
        The public HTTPS URL of the generated image stored in Cloud Storage.
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return "Please provide a valid image prompt."

    try:
        genai_client = genai.Client(vertexai=True, location="global")
        response = genai_client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=clean_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"]
            ),
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not image_bytes:
            return f"Failed to generate image for prompt: '{clean_prompt}'."

        ext = "jpg" if "jpeg" in mime_type or "jpg" in mime_type else "png"
        filename = f"destination_{uuid.uuid4().hex[:8]}.{ext}"

        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload image bytes directly to public GCS bucket without writing local files
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return (
            f"Successfully generated image for '{clean_prompt}'.\n"
            f"Public Image URL: {public_url}"
        )
    except Exception as e:
        return f"Image generation error: {str(e)}"


async def generate_destination_video(prompt: str, tool_context: ToolContext) -> str:
    """Generates a short travel video for a destination or attraction using gemini-omni-flash-preview in the global region, saves it as an artifact, uploads to GCS, and returns its public URL.

    Args:
        prompt: Detailed description of the travel scene, attraction, or destination video preview to generate.

    Returns:
        The public HTTPS URL of the generated video stored in Cloud Storage.
    """
    clean_prompt = prompt.strip()
    if not clean_prompt:
        return "Please provide a valid video prompt."

    try:
        genai_client = genai.Client(vertexai=True, location="global")
        response = genai_client.models.generate_content(
            model="gemini-omni-flash-preview",
            contents=clean_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "VIDEO"]
            ),
        )

        video_bytes = None
        mime_type = "video/mp4"

        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    raw_data = part.inline_data.data
                    if isinstance(raw_data, str):
                        import base64
                        video_bytes = base64.b64decode(raw_data)
                    else:
                        video_bytes = raw_data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break

        if not video_bytes:
            return f"Failed to generate video for prompt: '{clean_prompt}'."

        ext = "mp4"
        if "webm" in mime_type:
            ext = "webm"
        filename = f"destination_video_{uuid.uuid4().hex[:8]}.{ext}"

        # 1. Save with tool_context.save_artifact for Playground Artifacts panel
        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 2. Upload video bytes directly to public GCS bucket without writing local files
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return (
            f"Successfully generated video for '{clean_prompt}'.\n"
            f"Public Video URL: {public_url}"
        )
    except Exception as e:
        return f"Video generation error: {str(e)}"




def geocode_address(address: str) -> str:
    """Converts a physical address, landmark, or location query into geographic coordinates using the Google Maps Geocoding API.

    Args:
        address: Address or landmark name (e.g. 'Eiffel Tower, Paris', 'Shibuya Crossing, Tokyo').

    Returns:
        Formatted summary with address, latitude, longitude, and place ID.
    """
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not maps_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured."

    addr_clean = address.strip()
    if not addr_clean:
        return "Please provide a valid address or landmark name."

    try:
        url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(addr_clean)}&key={maps_key}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if data.get("status") != "OK" or not data.get("results"):
            return f"Geocoding failed for '{addr_clean}'. Status: {data.get('status', 'UNKNOWN')}"

        result = data["results"][0]
        formatted_address = result.get("formatted_address", addr_clean)
        loc = result.get("geometry", {}).get("location", {})
        place_id = result.get("place_id", "N/A")

        return (
            f"Location Name/Address: {formatted_address}\n"
            f"Latitude: {loc.get('lat')}\n"
            f"Longitude: {loc.get('lng')}\n"
            f"Place ID: {place_id}"
        )
    except Exception as e:
        return f"Geocoding API error: {str(e)}"


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "tourist_attraction",
    radius_meters: float = 1000.0,
) -> str:
    """Finds nearby places of a specific type around a location using the Google Places API (New) searchNearby REST endpoint.

    Args:
        latitude: Latitude coordinate (e.g. 48.85837).
        longitude: Longitude coordinate (e.g. 2.29448).
        place_type: Type of place to search for (e.g. 'restaurant', 'tourist_attraction', 'museum', 'cafe', 'park').
        radius_meters: Search radius in meters (default 1000.0).

    Returns:
        Formatted list of nearby places with name, formatted address, and location coordinates.
    """
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "").strip()
    if not maps_key:
        return "Error: GOOGLE_MAPS_API_KEY environment variable is not configured."

    url = "https://places.googleapis.com/v1/places:searchNearby"
    body = {
        "includedTypes": [place_type.strip().lower()],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": float(radius_meters),
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": maps_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        places = data.get("places", [])
        if not places:
            return f"No nearby '{place_type}' places found within {radius_meters}m radius."

        output = []
        for p in places:
            name = p.get("displayName", {}).get("text", "Unknown Name")
            address = p.get("formattedAddress", "N/A")
            loc = p.get("location", {})
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            output.append(
                f"• Name: {name}\n  Address: {address}\n  Location: Lat {lat}, Lng {lng}"
            )

        return f"Nearby '{place_type}' places:\n" + "\n\n".join(output)
    except Exception as e:
        return f"Places API (New) error: {str(e)}"


def get_city_geodata(city_name: str) -> str:
    """Fetches real geographic, demographic, and timezone data for a city using the Open-Meteo Geocoding public API.

    Args:
        city_name: The name of the city to look up (e.g. 'Tokyo', 'Paris', 'Barcelona').

    Returns:
        A string summarizing population, timezone, coordinates, region, and country data.
    """
    city_clean = city_name.strip()
    if not city_clean:
        return "Please provide a valid city name."

    # Reads API key from environment variable if configured, or uses free public access
    api_key = os.getenv("OPEN_METEO_API_KEY", "")

    try:
        encoded_name = urllib.parse.quote(city_clean)
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_name}&count=1&language=en&format=json"
        if api_key:
            url += f"&apikey={api_key}"

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        results = data.get("results")
        if not results:
            return f"No geographical data found for '{city_clean}'."

        city_data = results[0]
        pop = city_data.get("population")
        pop_str = f"{pop:,}" if isinstance(pop, int) else "N/A"

        return (
            f"City: {city_data.get('name')}, {city_data.get('country')} ({city_data.get('country_code', '')})\n"
            f"Region/State: {city_data.get('admin1', 'N/A')}\n"
            f"Population: {pop_str}\n"
            f"Timezone: {city_data.get('timezone', 'N/A')}\n"
            f"Coordinates: {city_data.get('latitude')}, {city_data.get('longitude')}\n"
            f"Elevation: {city_data.get('elevation', 'N/A')} meters"
        )
    except Exception as e:
        return f"Error fetching city data for '{city_clean}': {str(e)}"


def convert_currency(amount: float, from_currency: str = "USD", to_currency: str = "EUR") -> str:
    """Converts an amount from one currency to another using live exchange rates.

    Args:
        amount: The numerical monetary amount to convert (e.g. 150.0).
        from_currency: 3-letter currency code to convert from (e.g. 'USD', 'EUR', 'JPY').
        to_currency: 3-letter currency code to convert to (e.g. 'JPY', 'USD', 'EUR').

    Returns:
        A string summarizing the converted amount and current exchange rate.
    """
    from_code = from_currency.strip().upper()
    to_code = to_currency.strip().upper()

    try:
        url = f"https://open.er-api.com/v6/latest/{from_code}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if data.get("result") != "success":
            return f"Unable to fetch exchange rates for {from_code}."

        rates = data.get("rates", {})
        if to_code not in rates:
            return f"Unsupported target currency code: '{to_code}'."

        rate = rates[to_code]
        converted = amount * rate
        return (
            f"{amount:,.2f} {from_code} = {converted:,.2f} {to_code} "
            f"(Exchange rate: 1 {from_code} = {rate:,.4f} {to_code})"
        )
    except Exception as e:
        return f"Currency conversion error: {str(e)}"


def search_destinations(country: str = "", max_budget_usd: int = 0) -> str:
    """Searches the Firestore database for travel destinations matching optional criteria.

    Args:
        country: Optional country name to filter destinations (e.g. 'Japan', 'France').
        max_budget_usd: Optional maximum daily budget in USD. If greater than 0, filters results.

    Returns:
        A formatted string listing the matching travel destinations.
    """
    collection_ref = db.collection("destinations")
    docs = collection_ref.stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        if country and country.lower() not in data.get("country", "").lower():
            continue
        if max_budget_usd > 0 and data.get("average_cost_per_day_usd", 0) > max_budget_usd:
            continue
        results.append(
            f"• {data.get('name')} ({data.get('country')}) [ID: {doc.id}]: "
            f"Budget: {data.get('budget_level')} (~${data.get('average_cost_per_day_usd')}/day). "
            f"Description: {data.get('description')}"
        )

    if not results:
        return "No travel destinations found matching your criteria in Firestore."
    return "\n".join(results)


def get_destination_details(destination_id: str) -> str:
    """Retrieves full details for a specific destination by its document ID.

    Args:
        destination_id: The unique string ID of the destination (e.g. 'tokyo', 'paris').

    Returns:
        A detailed summary string of the requested destination.
    """
    doc_ref = db.collection("destinations").document(destination_id.lower().strip())
    doc = doc_ref.get()

    if not doc.exists:
        return f"Destination with ID '{destination_id}' was not found in Firestore."

    data = doc.to_dict()
    activities = ", ".join(data.get("top_activities", []))
    return (
        f"Destination: {data.get('name')}, {data.get('country')}\n"
        f"Description: {data.get('description')}\n"
        f"Budget Level: {data.get('budget_level')} (~${data.get('average_cost_per_day_usd')}/day)\n"
        f"Best Season: {data.get('best_season')}\n"
        f"Top Activities: {activities}"
    )


def add_destination(
    destination_id: str,
    name: str,
    country: str,
    description: str,
    budget_level: str,
    best_season: str,
    average_cost_per_day_usd: int,
) -> str:
    """Adds or updates a travel destination in the Firestore database.

    Args:
        destination_id: Unique string ID for the destination (e.g. 'rome').
        name: Common name of the city/destination (e.g. 'Rome').
        country: Country where the destination is located (e.g. 'Italy').
        description: A short overview of the destination.
        budget_level: Budget tier e.g. 'Low', 'Moderate', or 'High'.
        best_season: Best time of year to visit.
        average_cost_per_day_usd: Estimated daily cost in USD.

    Returns:
        Confirmation message upon saving to Firestore.
    """
    dest_data = {
        "id": destination_id.lower().strip(),
        "name": name,
        "country": country,
        "description": description,
        "budget_level": budget_level,
        "best_season": best_season,
        "average_cost_per_day_usd": average_cost_per_day_usd,
        "top_activities": [],
    }
    db.collection("destinations").document(dest_data["id"]).set(dest_data)
    return f"Successfully added destination '{name}' ({dest_data['id']}) to Firestore database."


def get_weather(query: str) -> str:
    """Simulates a web search. Use it get information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are Travel Concierge, a helpful AI travel assistant. "
        "Always remember and strictly observe the user's dietary preferences, medical restrictions, and allergies "
        "(such as food allergies, peanuts, gluten, shellfish, penicillin, etc.). "
        "Acknowledge any allergies mentioned by the user and use past conversation memories to personalize all "
        "restaurant, food, destination, and activity recommendations. "
        "Use your tools to generate travel destination images and short preview videos, geocode addresses, find nearby places, look up city geodata, "
        "convert currency values, search destinations, retrieve destination details, and add new travel recommendations into Firestore. "
        "You can also run Python calculations safely in a sandbox using code execution."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,

    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        generate_destination_image,
        generate_destination_video,
        geocode_address,
        find_nearby_places,
        get_city_geodata,
        convert_currency,
        search_destinations,
        get_destination_details,
        add_destination,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)


app = App(
    root_agent=root_agent,
    name="app",
)

