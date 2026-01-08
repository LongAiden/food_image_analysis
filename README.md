# Food Image Analysis API

FastAPI service that analyzes food images with Google Gemini and returns structured nutrition facts. Images are validated, analyzed, stored in Supabase Storage, and results are persisted in Supabase Postgres.

## Features

- AI-powered analysis via Gemini (structured output)
- Upload via multipart, base64 JSON, or Telegram file_id
- Supabase Storage for images + Supabase Postgres for results/history
- **Strict data validation** - All nutritional values must be > 0
- **Comprehensive test suite** - 50+ tests with 1962 lines of test code
- FastAPI docs (`/docs`, `/redoc`) and health check
- Logfire instrumentation for observability

## Tech Stack

- FastAPI, Pydantic v2, Pillow
- Google Generative AI (Gemini)
- Supabase (Postgres + Storage)
- Logfire
- Uvicorn

## Project Structure

```
food_image_analysis/
├─ main.py                      # FastAPI entrypoint (lifespan + routes)
├─ backend/
│  ├─ config.py                 # Pydantic Settings (env-validated config)
│  ├─ models/
│  │  └─ models.py              # Pydantic models & schemas
│  └─ services/
│     ├─ image_utils.py         # Image validation/normalization helpers
│     ├─ gemini_analyzer.py     # Gemini AI integration
│     └─ supabase_service.py    # Supabase DB & Storage services
├─ frontend/                    # (optional frontend)
├─ images/                      # Sample images
├─ requirements.txt             # Python dependencies
├─ .env.example                 # Environment variables template
├─ README.md
└─ WORKFLOW.md                  # Detailed workflow guide
```

## Installation

### Prerequisites

- Python 3.9+
- Supabase account (service role key)
- Google AI API key (Gemini)
- Logfire token (optional)
- Telegram bot token (optional, for Telegram uploads)

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
TELEGRAM_BOT_TOKEN=optional-telegram-token
# Optional overrides
ALLOWED_ORIGINS=["http://localhost:3000"]
MAX_IMAGE_SIZE_MB=10
```

4. Set up Supabase database table (SQL):

```sql
CREATE TABLE IF NOT EXISTS food_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_path TEXT NOT NULL,
    food_name TEXT NOT NULL,
    calories FLOAT NOT NULL,
    sugar FLOAT NOT NULL,
    protein FLOAT NOT NULL,
    carbs FLOAT NOT NULL,
    fat FLOAT NOT NULL,
    fiber FLOAT NOT NULL,
    health_score INT,
    others TEXT NOT NULL,
    raw_result JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
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

```bash
python main.py
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
- **POST** `/analyze-telegram` — supply `file_id` from Telegram

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

Telegram (file_id):
```bash
curl -X POST "http://localhost:8000/analyze-telegram?file_id=<telegram_file_id>"
```

Telegram bot delivery:
- If you provide `TELEGRAM_WEBHOOK_URL`, the server registers the webhook on startup.
- If no webhook URL is set, the app now falls back to long-polling automatically — just run `python main.py` and send the bot a photo.
- Optional: set `ENABLE_NGROK=true` (and ensure `ngrok` is on PATH). On startup the app will open a tunnel on `NGROK_PORT` (default 8000), auto-set `TELEGRAM_WEBHOOK_URL`, and register the webhook for you.

History:
```bash
curl "http://localhost:8000/history?limit=5"
```

### Response Format

```json
{
  "analysis_id": "123e4567-e89b-12d3-a456-426614174000",
  "nutrition": {
    "food_name":"pizza",
    "calories": 320.0,
    "sugar": 8.5,
    "protein": 28.0,
    "carbs": 12.0,
    "fat": 10.0,
    "fiber": 12.0,
    "others": "This food contains...",
    "health_score":80,
    ...
  },
  "image_url": "https://xxx.supabase.co/storage/v1/object/public/food-images/...",
  "timestamp": "2025-10-15T00:00:00Z"
}
```

## How It Works (pipeline)
1. Login with a credential in `.env` ![Telegram](images/telegram_interaction_1.png)
2. Users can select various commands such as `/summary`, `/logout` ![Telegram](images/telegram_interaction_5.png)

3. Upload a single food image on the Telegram chatbot
4. Validate image (size/format) and normalize (RGBA→RGB, re-encode, data URI).
5. Send to Gemini for structured `NutritionAnalysis`.
6. Upload processed image to Supabase Storage (public URL).
![Supabase Bucket](images/supabse_buckets.png)
7. Persist results + image URL in Supabase Postgres.
![Supabase](images/supabse_db.png)
8. Return `FoodAnalysisResponse` (analysis_id, nutrition, image_url, timestamp).
![Telegram](images/telegram_interaction_4.png)
9. Logfire check:
![Logfire](images/logfire_2.png)
10. Users choose to logout ![Telegram](images/telegram_interaction_2.png)

## Key Components

- `backend/config.py`: Typed Settings loader (env validation), CORS origins, max image size.
- `backend/services/image_utils.py`: Shared image validation/normalization + data URI prep.
- `backend/services/gemini_analyzer.py`: Gemini integration for structured nutrition output.
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
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (for `/analyze-telegram`) | No |
| `TELEGRAM_WEBHOOK_URL` | Public HTTPS URL to set webhook automatically (optional) | No |
| `ALLOWED_ORIGINS` | CORS allowlist (JSON array) | No |
| `MAX_IMAGE_SIZE_MB` | Max upload size in MB | No |

### Supported Image Formats

- JPEG / JPG, PNG, WEBP, GIF
- Default max size: 10 MB (override via `MAX_IMAGE_SIZE_MB`)

## Development

### Testing

The project includes a comprehensive test suite with 50+ tests covering unit and integration testing.

**Test Coverage:**
- 37 integration tests for API endpoints
- 33 unit tests for database service
- 10+ integration tests for Supabase service
- Edge case validation (None, 0, invalid types)
- Error handling verification

**Running Tests:**

```bash
# Run all tests
pytest

# Run specific test types
pytest -m integration  # Integration tests only
pytest -m unit         # Unit tests only

# Run specific test file
pytest tests/unit/test_database_service.py

# Run with coverage report
pytest --cov=backend --cov-report=html
```

**Test Files:**
- `tests/unit/test_database_service.py` - Database service unit tests (558 lines)
- `tests/unit/test_analysis_service.py` - Analysis service unit tests (410 lines)
- `tests/integration/test_api_endpoints.py` - API endpoint tests (540 lines)
- `tests/integration/test_supabase_service.py` - Supabase integration tests (297 lines)
- `tests/integration/test_intergration_database_service.py` - Database integration tests (157 lines)

### Data Validation

The `NutritionAnalysis` model enforces strict validation:

```python
- calories: must be > 0
- sugar: must be > 0
- protein: must be > 0
- carbs: must be > 0
- fat: must be > 0
- fiber: must be > 0
- health_score: must be between 1-100 (if provided)
```

Invalid values will raise a `ValidationError` from Pydantic.

### CORS Configuration

- Defaults to `ALLOWED_ORIGINS` from settings (e.g., `["http://localhost:3000"]`).
- For production, set explicit origins in `.env`.

## Monitoring

- Logfire instrumentation is enabled; configure `LOGFIRE_WRITE_TOKEN` to send data.

## Limitations & Considerations

**Current State:** This project is designed for **personal use** and **development/learning purposes**. It is **not production-ready** for multi-user or high-scale deployments.

### Scalability

- ⚠️ **Single Python Process** - No containerization (Docker) or orchestration (Kubernetes)
- ⚠️ **Vertical Scaling Only** - Limited to single server resources
- ⚠️ **No Load Balancing** - Cannot distribute traffic across multiple instances
- ⚠️ **In-Memory Sessions** - Telegram sessions stored in `app.state` (lost on restart)

**Impact:**
- Cannot handle high concurrent requests efficiently
- Limited by single CPU/memory constraints
- Not suitable for production traffic

### Request Handling

- ⚠️ **No Request Queuing** - Large batches of simultaneous uploads may overwhelm the server
- ⚠️ **No Rate Limiting** - No protection against abuse or DoS
- ⚠️ **Synchronous Image Processing** - Large images may block other requests
- ⚠️ **No Retry Mechanism** - Failed uploads require manual retry

**Impact:**
- May experience slowdowns or timeouts under load
- Vulnerable to resource exhaustion
- No graceful degradation

### Deployment

- ⚠️ **Local Development Only** - No cloud deployment configuration
- ⚠️ **No CI/CD Pipeline** - Manual deployment required
- ⚠️ **No Environment Separation** - Single .env file for all environments
- ⚠️ **No Health Monitoring** - Basic `/health` endpoint only
- ⚠️ **No Auto-Scaling** - Cannot dynamically adjust to traffic

**Impact:**
- Requires manual server setup and maintenance
- No automated deployments or rollbacks
- No infrastructure-as-code

### Multi-User Support

- ⚠️ **Single User Design** - No user isolation or multi-tenancy
- ⚠️ **No Authentication** - Telegram uses simple password, API has no auth
- ⚠️ **No Authorization** - All users can see all data
- ⚠️ **Shared Database** - No per-user data segregation
- ⚠️ **No Usage Quotas** - No limits per user

**Impact:**
- **NOT SUITABLE for multi-user production use**
- All users share the same database and storage
- No privacy or data isolation
- No billing or usage tracking

### Recommended Use Cases

✅ **Good For:**
- Personal nutrition tracking
- Learning FastAPI and AI integration
- Prototyping food analysis features
- Development and testing
- Single-user Telegram bot

❌ **Not Suitable For:**
- Production SaaS applications
- Multi-tenant systems
- High-traffic public APIs
- Commercial deployment
- Enterprise use cases

### Future Improvements (Roadmap)

To make this production-ready, consider:
- 🐳 Dockerization for containerized deployment
- ☸️ Kubernetes manifests for orchestration
- 🔐 Proper authentication (OAuth2, API keys)
- 👥 Multi-user support with data isolation
- 📊 Request queuing (Celery/Redis)
- 🚀 Cloud deployment (AWS/GCP/Azure)
- 📈 Horizontal auto-scaling
- 🔄 CI/CD pipeline (GitHub Actions)
- 💾 Caching layer (Redis)
- 📉 Rate limiting and quotas

## Error Handling

- `400` invalid image/validation
- `404` not found
- `500` analysis/database/storage errors
