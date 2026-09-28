# Travel Concierge Assistant

A conversational AI travel assistant powered by Google's Agent Development Kit (ADK) and deployed on Agent Platform. Travel Concierge helps travelers plan personalized travel itineraries, discover curated destinations, convert trip currencies, search nearby attractions, and generate AI visual & video previews.

![Travel Concierge Demo](demo.gif)

---

## Key Features & Implemented Capabilities

This project implements the following capabilities, backed directly by Google Cloud services and ADK tools in `app/agent.py`:

* **Cross-Session Long-Term Memory (Vertex AI Memory Bank)**
  * Powered by `VertexAiMemoryBankService` and `PreloadMemoryTool`.
  * Persists user dietary preferences, food allergies, travel budget style, and past visited cities across conversations.

* **Rich Interactive Cards (A2UI)**
  * Configured via `A2uiSchemaManager` and `BasicCatalog`.
  * Generates structured display cards for destination recommendations and travel itineraries directly inside the chat interface.

* **AI Image Generation**
  * Powered by `gemini-3.1-flash-lite-image` in the `global` region via `google-genai`.
  * Generates high-quality travel destination visual previews on demand.

* **AI Video Generation**
  * Powered by `gemini-omni-flash-preview` in the `global` region.
  * Generates short animated video previews of travel scenes and attractions.

* **Google Cloud Storage (GCS)**
  * Direct in-memory streaming of generated image and video bytes to a public Cloud Storage bucket (`travel-concierge-media-...`).
  * Returns public HTTPS media links without writing local temporary files.

* **Firestore Database Catalog**
  * Integrated via `google.cloud.firestore`.
  * Enables searching, retrieving, and saving destination records to a Firestore database.

* **Google Maps & Places (New) Integration**
  * Geocodes landmarks and physical addresses using Google Maps Geocoding API (`geocode_address`).
  * Searches nearby tourist attractions, restaurants, and places using Google Places API v1 (`find_nearby_places`).

* **Currency Conversion & Sandbox Calculations**
  * Performs real-time foreign exchange conversions across major global currencies (`convert_currency`).
  * Runs complex itinerary budget math securely inside an `AgentEngineSandboxCodeExecutor`.

* **Real-time Weather & Local Time**
  * Fetches current weather forecasts and city local time summaries (`get_weather`, `get_current_time`).

---

## Planned / Future Capabilities

The following features were outlined in initial design briefs but are not yet implemented in the current codebase:

* **Live Flight Booking Engine Integration**: *(Planned, not yet implemented)*
* **Hotel Inventory Reservation System**: *(Planned, not yet implemented)*

---

## Project Structure

```
travel-concierge/
├── app/
│   ├── agent.py            # Core ADK agent definition, tools, and Memory Bank builder
│   ├── a2ui_utils.py       # A2UI callback and schema response processor
│   └── __init__.py
├── frontend/
│   ├── main.py             # FastAPI proxy connecting browser to deployed Agent Runtime
│   ├── requirements.txt    # Frontend Python dependencies
│   └── static/
│       └── index.html      # Responsive chat UI with Welcome Hero & prompt chips
├── agents-cli-manifest.yaml # Agent Platform deployment configuration
├── deployment_metadata.json # Deployed Agent Engine resource IDs
└── demo.gif                # Animated recording of the interactive chat UI
```

---

## Local Setup & Run Instructions

### Prerequisites
- Python 3.11+
- Google Cloud SDK (`gcloud` CLI)
- Configured GCP Project with Vertex AI and Firestore enabled

### 1. Install Dependencies
```bash
pip install -r requirements.txt
pip install -r frontend/requirements.txt
```

### 2. Configure Environment Variables
Set the required environment variables in your terminal or a `.env` file:
```bash
export GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
export GOOGLE_MAPS_API_KEY="<your-google-maps-api-key>"
export AGENT_ENGINE_RESOURCE_NAME="projects/<project-id>/locations/us-east1/reasoningEngines/<engine-id>"
export AGENT_DIRECTORY="app"
```

### 3. Run the Frontend Locally
Start the FastAPI proxy server locally:
```bash
cd frontend
python main.py
```
Open your browser and navigate to the local server address printed in the terminal (default port 8080).

---

## Deployment Instructions

### Deploy Agent to Agent Platform (Agent Runtime)
To deploy or update the agent backend on Vertex AI:
```bash
agents-cli deploy \
  --project <your-gcp-project-id> \
  --region us-east1 \
  --update-env-vars GOOGLE_MAPS_API_KEY=<your-google-maps-api-key>
```

### Deploy Frontend to Cloud Run
To deploy the chat proxy interface to Cloud Run:
```bash
cd frontend
gcloud run deploy travel-concierge-frontend \
  --source . \
  --region us-east1 \
  --project <your-gcp-project-id> \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<your-agent-engine-resource-name>",AGENT_DIRECTORY="app"
```
