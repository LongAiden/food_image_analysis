# Food Image Analysis API

FastAPI service that analyzes food images with Google Gemini and returns structured nutrition facts. Images are validated, analyzed, stored in Supabase Storage, and results are persisted in Supabase Postgres.

## Features

- AI-powered analysis via Gemini 2.5 Flash (Pydantic-AI structured output)
- Upload via multipart or base64 JSON
- Supabase Storage for images + Supabase Postgres for results/history
- FastAPI docs (`/docs`, `/redoc`) and health check
- Logfire instrumentation for observability

## Tech Stack

- FastAPI, Pydantic v2, Pydantic-AI, Pillow
- Gemini 2.5 Flash (Google Generative AI)
- Supabase (Postgres + Storage)
- Logfire
- Uvicorn

## Project Structure

```
food_image_analysis/
+- main.py                      # FastAPI entrypoint (lifespan + routes)
+- backend/
¦  +- config.py                 # Pydantic Settings (env-validated config)
¦  +- models/
¦  ¦  +- models.py              # Pydantic models & schemas
¦  +- services/
¦     +- image_utils.py         # Image validation/normalization helpers
¦     +- gemini_analyzer.py     # Gemini AI integration (Pydantic-AI)
¦     +- supabase_service.py    # Supabase DB & Storage services
+- frontend/                    # (optional frontend)
+- images/                      # Sample images
+- requirements.txt             # Python dependencies
+- .env.example                 # Environment variables template
+- README.md
+- WORKFLOW.md                  # Detailed workflow guide
```

## Installation

### Prerequisites

- Python 3.9+
- Supabase account (service role key)
- Google AI API key (Gemini)
- Logfire token (optional, for monitoring)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd food_image_analysis
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` from the example and fill required values:
```bash
cp .env.example .env
```

Key env vars (see `backend/config.py` for full list):
```env
SUPABASE_PROJECT_URL=...
SUPABASE_SERVICE_KEY=...
SUPABASE_BUCKETS=food-images
SUPABASE_TABLE=food_analyses
GOOGLE_API_KEY=...
LOGFIRE_WRITE_TOKEN=optional-logfire-token
# Optional overrides
ALLOWED_ORIGINS=["http://localhost:3000"]
MAX_IMAGE_SIZE_MB=10
```

4. Set up Supabase database table (SQL):

```sql
CREATE TABLE IF NOT EXISTS food_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_path TEXT NOT NULL,
    calories FLOAT NOT NULL,
    sugar FLOAT NOT NULL,
    protein FLOAT NOT NULL,
    others TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_created_at ON food_analyses(created_at DESC);
ALTER TABLE food_analyses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations" ON food_analyses FOR ALL USING (true) WITH CHECK (true);
```

## Usage

### Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API: `http://localhost:8000`

### API Endpoints

#### System
- **GET** `/health`
- **GET** `/docs`
- **GET** `/redoc`

#### Analysis
- **POST** `/analyze` — multipart upload
- **POST** `/analyze-base64` — JSON with base64 image

#### History
- **GET** `/analysis/{analysis_id}`
- **GET** `/history?limit=10&offset=0`
- **DELETE** `/analysis/{analysis_id}`

#### Statistics
- **GET** `/statistics`

### Example Usage

Upload (multipart):
```bash
curl -X POST "http://localhost:8000/analyze" \
  -F "file=@path/to/food_image.jpg"
```

Upload (base64 JSON):
```python
import base64, requests
with open("food_image.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()
resp = requests.post(
    "http://localhost:8000/analyze-base64",
    json={"image_data": image_data, "filename": "food_image.jpg"},
)
print(resp.json())
```

History:
```bash
curl "http://localhost:8000/history?limit=5"
```

### Response Format

```json
{
  "analysis_id": "123e4567-e89b-12d3-a456-426614174000",
  "nutrition": {
    "calories": 320.0,
    "sugar": 8.5,
    "protein": 28.0,
    "others": "Carbohydrates: 22g, Fat: 12g (Saturated: 2g, Unsaturated: 10g), Fiber: 5g, Sodium: 450mg..."
  },
  "image_url": "https://xxx.supabase.co/storage/v1/object/public/food-images/...",
  "timestamp": "2025-10-15T00:00:00Z"
}
```

## How It Works (pipeline)

1. Validate image (size/format) and normalize (RGBA?RGB, re-encode, data URI).
2. Send to Gemini via Pydantic-AI for structured `NutritionAnalysis`.
3. Upload processed image to Supabase Storage (public URL).
4. Persist results + image URL in Supabase Postgres.
5. Return `FoodAnalysisResponse` (analysis_id, nutrition, image_url, timestamp).

## Key Components

- `backend/config.py`: Typed Settings loader (env validation), CORS origins, max image size.
- `backend/services/image_utils.py`: Shared image validation/normalization + data URI prep.
- `backend/services/gemini_analyzer.py`: Gemini + Pydantic-AI structured nutrition output.
- `backend/services/supabase_service.py`: Supabase DB/Storage with async-safe thread wrapping.

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_PROJECT_URL` | Supabase project URL | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Yes |
| `SUPABASE_BUCKETS` | Storage bucket name | Yes |
| `SUPABASE_TABLE` | Database table name | Yes |
| `GOOGLE_API_KEY` | Google AI API key for Gemini | Yes |
| `LOGFIRE_WRITE_TOKEN` | Logfire token (optional) | No |
| `ALLOWED_ORIGINS` | CORS allowlist (JSON array) | No |
| `MAX_IMAGE_SIZE_MB` | Max upload size in MB | No |

### Supported Image Formats

- JPEG / JPG, PNG, WEBP, GIF
- Default max size: 10 MB (override via `MAX_IMAGE_SIZE_MB`)

## Development

### Testing

```bash
pytest
```

### CORS Configuration

- Defaults to `ALLOWED_ORIGINS` from settings (e.g., `["http://localhost:3000"]`).
- For production, set explicit origins in `.env`.

## Monitoring

- Logfire instrumentation is enabled; configure `LOGFIRE_WRITE_TOKEN` to send data.

## Error Handling

- `400` invalid image/validation
- `404` not found
- `500` analysis/database/storage errors

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions, please open an issue on the repository.
