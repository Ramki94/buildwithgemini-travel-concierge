"""Seed script to populate Firestore with sample travel destinations."""

import logging
from google.cloud import firestore

# Hardcoded GCP Project ID (crucial for Agent Platform compatibility)
PROJECT_ID = "qwiklabs-gcp-02-ad44f2a2ea8f"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAMPLE_DESTINATIONS = [
    {
        "id": "tokyo",
        "name": "Tokyo",
        "country": "Japan",
        "description": "A vibrant metropolis blending ultra-modern technology with traditional temples and world-class culinary experiences.",
        "budget_level": "High",
        "top_activities": ["Visit Senso-ji Temple", "Explore Akihabara & Shibuya Crossing", "Dine at Tsukiji Outer Market"],
        "best_season": "Spring & Autumn",
        "average_cost_per_day_usd": 180,
    },
    {
        "id": "kyoto",
        "name": "Kyoto",
        "country": "Japan",
        "description": "Japan's cultural heartland, renowned for thousands of classical Buddhist temples, gardens, imperial palaces, and traditional wooden houses.",
        "budget_level": "Moderate",
        "top_activities": ["Walk through Fushimi Inari Shrine", "Stroll Arashiyama Bamboo Grove", "Experience a traditional Tea Ceremony"],
        "best_season": "Spring & Autumn",
        "average_cost_per_day_usd": 140,
    },
    {
        "id": "paris",
        "name": "Paris",
        "country": "France",
        "description": "The City of Light, world-famous for art, gastronomy, iconic architecture, and romantic boulevard culture.",
        "budget_level": "High",
        "top_activities": ["Tour the Louvre Museum", "Climb Eiffel Tower", "Cruise along the Seine River"],
        "best_season": "Spring & Summer",
        "average_cost_per_day_usd": 200,
    },
    {
        "id": "barcelona",
        "name": "Barcelona",
        "country": "Spain",
        "description": "Catalonia's vibrant seaside capital, known for Antoni Gaudí's whimsical architecture, lively tapas bars, and Mediterranean beaches.",
        "budget_level": "Moderate",
        "top_activities": ["Admire Sagrada Família", "Stroll Park Güell", "Relax on Barceloneta Beach"],
        "best_season": "Late Spring & Early Autumn",
        "average_cost_per_day_usd": 130,
    },
    {
        "id": "bali",
        "name": "Bali",
        "country": "Indonesia",
        "description": "An Indonesian paradise celebrated for forested volcanic mountains, iconic rice paddies, pristine beaches, and spiritual coral reefs.",
        "budget_level": "Low",
        "top_activities": ["Surf in Canggu", "Visit Sacred Monkey Forest Sanctuary in Ubud", "Explore Tegallalang Rice Terraces"],
        "best_season": "Dry Season (April - October)",
        "average_cost_per_day_usd": 70,
    },
]


def seed_database():
    """Populates the 'destinations' collection in Firestore."""
    logger.info(f"Connecting to Firestore for project '{PROJECT_ID}'...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection("destinations")

    for dest in SAMPLE_DESTINATIONS:
        doc_id = dest["id"]
        doc_ref = collection_ref.document(doc_id)
        doc_ref.set(dest)
        logger.info(f"Successfully seeded destination: {dest['name']} ({doc_id})")

    logger.info("Firestore database seeding completed successfully!")


if __name__ == "__main__":
    seed_database()
