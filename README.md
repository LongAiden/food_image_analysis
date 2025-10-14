# Food Image Analysis API

A FastAPI-based service that analyzes food images using Google's Gemini AI to extract detailed nutritional information. Upload a food photo and get instant estimates of calories, protein, sugar, and other nutritional details.

## Features

- **AI-Powered Analysis**: Uses Gemini 2.5 Flash with Pydantic AI for structured nutritional analysis
- **Image Upload**: Supports both file upload and base64-encoded image submission
- **Cloud Storage**: Automatic image storage in Supabase Storage
- **Database Persistence**: Save and retrieve analysis history with PostgreSQL via Supabase
- **Comprehensive API**: RESTful endpoints for analysis, history, statistics, and more
- **Observability**: Built-in monitoring and logging with Logfire
- **Interactive Docs**: Auto-generated OpenAPI documentation with Swagger UI

## Tech Stack

- **Framework**: FastAPI 0.115.0
- **AI Model**: Google Gemini 2.5 Flash via Pydantic AI
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **Monitoring**: Logfire
- **Image Processing**: Pillow (PIL)
- **Server**: Uvicorn

## Project Structure

```
food_image_analysis/
├── main.py                 # FastAPI application entry point
├── backend/
│   ├── models/
│   │   └── models.py      # Pydantic models and schemas
│   ├── services/
│   │   ├── gemini_analyzer.py    # Gemini AI integration
│   │   └── supabase_service.py   # Database & Storage services
│   └── workflow/          # Additional workflows
├── frontend/              # Frontend application (if any)
├── images/               # Sample images for testing
├── requirements.txt      # Python dependencies
├── .env.example         # Environment variables template
└── README.md            # This file
```

## Installation

### Prerequisites

- Python 3.8+
- Supabase account
- Google AI API key (for Gemini)
- Logfire account (optional, for monitoring)

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

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. Configure environment variables in `.env`:
```env
# Supabase Configuration
SUPABASE_PROJECT_URL=your_supabase_url
SUPABASE_SERVICE_KEY=your_supabase_service_key
SUPABASE_BUCKETS=food-images
SUPABASE_TABLE=food_analyses

# Google AI API Key
GOOGLE_API_KEY=your_google_api_key

# Logfire (optional)
LOGFIRE_WRITE_TOKEN=your_logfire_token
```

5. Set up Supabase database table:

Run this SQL in your Supabase SQL Editor:

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

-- Add index for faster queries
CREATE INDEX IF NOT EXISTS idx_created_at ON food_analyses(created_at DESC);

-- Enable Row Level Security (optional)
ALTER TABLE food_analyses ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all operations
CREATE POLICY "Allow all operations" ON food_analyses
FOR ALL USING (true) WITH CHECK (true);
```

## Usage

### Running the Server

Start the development server:

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### API Endpoints

#### System

- **GET** `/health` - Health check endpoint
- **GET** `/docs` - Interactive API documentation (Swagger UI)
- **GET** `/redoc` - Alternative API documentation

#### Analysis

- **POST** `/analyze` - Analyze food image (multipart/form-data)
  - Upload a food image file
  - Returns nutritional analysis with calories, protein, sugar, and more

- **POST** `/analyze-base64` - Analyze food image from base64 data
  - Send base64-encoded image in JSON
  - Returns the same nutritional analysis

#### History

- **GET** `/analysis/{analysis_id}` - Get specific analysis by UUID
- **GET** `/history?limit=10&offset=0` - Get recent analysis history
- **DELETE** `/analysis/{analysis_id}` - Delete specific analysis

#### Statistics

- **GET** `/statistics` - Get aggregated statistics
  - Total analyses count
  - Average calories, protein, and sugar

### Example Usage

#### Upload and Analyze Image (cURL)

```bash
curl -X POST "http://localhost:8000/analyze" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@path/to/food_image.jpg"
```

#### Analyze Base64 Image (Python)

```python
import requests
import base64

# Read and encode image
with open("food_image.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

# Send request
response = requests.post(
    "http://localhost:8000/analyze-base64",
    json={
        "image_data": image_data,
        "filename": "food_image.jpg"
    }
)

result = response.json()
print(f"Calories: {result['nutrition']['calories']}")
print(f"Protein: {result['nutrition']['protein']}g")
print(f"Sugar: {result['nutrition']['sugar']}g")
```

#### Get Analysis History

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

## How It Works

1. **Image Upload**: User uploads a food image via API endpoint
2. **Validation**: Image is validated for size and format
3. **AI Analysis**: Gemini AI analyzes the image using Pydantic AI with structured output
4. **Storage**: Image is uploaded to Supabase Storage with unique filename
5. **Database**: Analysis results are saved to Supabase PostgreSQL database
6. **Response**: Structured nutritional data is returned to the user

## Key Components

### GeminiAnalyzer (backend/services/gemini_analyzer.py)
- Integrates Gemini 2.5 Flash model via Pydantic AI
- Validates and processes images (handles RGBA to RGB conversion)
- Provides structured nutritional analysis output
- Supports both file upload and base64 input

### StorageService (backend/services/supabase_service.py)
- Manages image uploads to Supabase Storage
- Generates unique filenames with timestamps
- Handles bucket creation and file management
- Returns public URLs for stored images

### DatabaseService (backend/services/supabase_service.py)
- CRUD operations for analysis records
- History retrieval with pagination
- Statistical aggregations
- Async database operations

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SUPABASE_PROJECT_URL` | Your Supabase project URL | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase service role key | Yes |
| `SUPABASE_BUCKETS` | Storage bucket name | Yes |
| `SUPABASE_TABLE` | Database table name | Yes |
| `GOOGLE_API_KEY` | Google AI API key for Gemini | Yes |
| `LOGFIRE_WRITE_TOKEN` | Logfire monitoring token | Optional |

### Supported Image Formats

- JPEG / JPG
- PNG
- WEBP
- GIF

Maximum file size: 10MB

## Development

### Testing

The project includes pytest for testing:

```bash
pytest
```

### CORS Configuration

CORS is configured to allow all origins by default. Update main.py:67-73 for production:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Monitoring

The application is instrumented with Logfire for observability:

- Request/response logging
- Performance metrics
- Error tracking
- Custom event logging

Access your Logfire dashboard to view metrics and traces.

## Error Handling

The API includes comprehensive error handling:

- `400` - Bad Request (invalid image, validation errors)
- `404` - Not Found (analysis not found)
- `500` - Internal Server Error (analysis failures, database errors)

All errors return structured JSON responses with detail messages.

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For issues and questions, please open an issue on the repository.

## Acknowledgments

- Built with FastAPI and Pydantic AI
- Powered by Google Gemini AI
- Infrastructure by Supabase
- Monitoring by Logfire
