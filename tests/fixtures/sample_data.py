"""Sample data for tests."""

from datetime import datetime
from uuid import uuid4

# Sample nutrition analysis
SAMPLE_NUTRITION = {
    "food_name": "Grilled Chicken Salad",
    "calories": 320.0,
    "sugar": 8.5,
    "protein": 28.0,
    "carbs": 22.0,
    "fat": 12.0,
    "fiber": 5.0,
    "health_score": 85,
    "others": "Healthy meal with leafy greens"
}

# Sample database record
SAMPLE_DB_RECORD = {
    "id": str(uuid4()),
    "image_path": "https://example.com/image.jpg",
    "food_name": "Grilled Chicken Salad",
    "calories": 320.0,
    "sugar": 8.5,
    "protein": 28.0,
    "carbs": 22.0,
    "fat": 12.0,
    "fiber": 5.0,
    "health_score": 85,
    "others": "Healthy meal with leafy greens",
    "raw_result": SAMPLE_NUTRITION,
    "created_at": datetime.utcnow().isoformat(),
    "timestamp": datetime.utcnow().isoformat(),
}

# Sample statistics
SAMPLE_STATISTICS = {
    "start_date": "2025-12-24T00:00:00",
    "total_meals": 5,
    "avg_calories": 450.5,
    "avg_protein": 25.3,
    "avg_sugar": 15.2,
    "avg_carbs": 55.1,
    "avg_fat": 18.7,
    "avg_fiber": 8.3,
    "avg_health_score": 75.2
}

# Sample image data (tiny 1x1 pixel PNG)
SAMPLE_IMAGE_BYTES = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
    b'\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)
