import os
import base64
import logfire
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from uuid import UUID
from contextlib import asynccontextmanager

from backend.models.models import (
    FoodAnalysisRequest,
    FoodAnalysisResponse
)
from backend.services.gemini_analyzer import GeminiAnalyzer
from backend.services.supabase_service import StorageService, DatabaseService

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_PROJECT_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
SUPABASE_BUCKET = os.getenv('SUPABASE_BUCKETS')
SUPABASE_TABLE = os.getenv('SUPABASE_TABLE')

LOGFIRE_TOKEN = os.getenv('LOGFIRE_WRITE_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Initialize Logfire
logfire.configure(token=LOGFIRE_TOKEN)
logfire.info("Starting Food Analysis API")


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context for app startup and shutdown"""
    # Startup
    logfire.info("🚀 Application starting up...")

    # Initialize services
    app.state.gemini_analyzer = GeminiAnalyzer(api_key=GOOGLE_API_KEY)
    app.state.storage_service = StorageService(
        url=SUPABASE_URL, key=SUPABASE_KEY, bucket_name=SUPABASE_BUCKET)
    app.state.database_service = DatabaseService(
        url=SUPABASE_URL, key=SUPABASE_KEY, table_name=SUPABASE_TABLE)

    logfire.info("✓ All services initialized")

    yield

    # Shutdown
    logfire.info("👋 Application shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Food Image Analysis API",
    description="API for analyzing food images using Gemini AI to extract nutritional information",
    version="1.0.0",
    lifespan=lifespan
)

# Instrument FastAPI with Logfire
logfire.instrument_fastapi(app)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "food-analysis-api",
        "version": "1.0.0"
    }


# Main analysis endpoint - accepts multipart/form-data (file upload)
@app.post("/analyze", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image(
    file: UploadFile = File(...,
                            description="Food image file (JPEG, PNG, WEBP)")
):
    """
    Analyze a food image and return nutritional information.

    - Accepts image file upload
    - Analyzes using Gemini AI
    - Stores image in Supabase
    - Saves analysis to database
    - Returns structured nutrition data
    """
    try:
        logfire.info(f"Received analysis request for file: {file.filename}")

        # Read file data
        image_data = await file.read()

        # Validate image
        app.state.gemini_analyzer.validate_image(image_data)

        # Analyze image with Gemini
        nutrition_analysis = await app.state.gemini_analyzer.analyze_image(
            image_data=image_data,
            filename=file.filename
        )

        # Upload to storage
        storage_result = app.state.storage_service.upload_image(
            image_data=image_data,
            filename=file.filename,
            content_type=file.content_type or "image/jpeg"
        )

        # Save to database
        db_record = await app.state.database_service.save_analysis(
            image_path=storage_result["url"],
            nutrition=nutrition_analysis
        )

        # Create response
        response = FoodAnalysisResponse(
            analysis_id=UUID(db_record["id"]),
            nutrition=nutrition_analysis,
            image_url=storage_result["url"],
            timestamp=db_record["created_at"]
        )

        logfire.info(f"✓ Analysis completed: {response.analysis_id}")

        return response

    except ValueError as e:
        logfire.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logfire.error(f"Analysis error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Analysis failed: {str(e)}")


# Alternative endpoint - accepts JSON with base64 encoded image
@app.post("/analyze-base64", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image_base64(request: FoodAnalysisRequest):
    """
    Analyze a food image from base64 encoded data.

    - Accepts base64 encoded image in JSON
    - Analyzes using Gemini AI
    - Stores image in Supabase
    - Saves analysis to database
    - Returns structured nutrition data
    """
    try:
        logfire.info(f"Received base64 analysis request: {request.filename}")

        # Decode base64
        if "," in request.image_data:
            request.image_data = request.image_data.split(",")[1]

        image_data = base64.b64decode(request.image_data)

        # Validate image
        app.state.gemini_analyzer.validate_image(image_data)

        # Analyze image with Gemini
        nutrition_analysis = await app.state.gemini_analyzer.analyze_image(
            image_data=image_data,
            filename=request.filename or "image.jpg"
        )

        # Upload to storage
        storage_result = app.state.storage_service.upload_image(
            image_data=image_data,
            filename=request.filename
        )

        # Save to database
        db_record = await app.state.database_service.save_analysis(
            image_path=storage_result["url"],
            nutrition=nutrition_analysis
        )

        # Create response
        response = FoodAnalysisResponse(
            analysis_id=UUID(db_record["id"]),
            nutrition=nutrition_analysis,
            image_url=storage_result["url"],
            timestamp=db_record["created_at"]
        )

        logfire.info(f"✓ Analysis completed: {response.analysis_id}")

        return response

    except ValueError as e:
        logfire.error(f"Validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logfire.error(f"Analysis error: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Analysis failed: {str(e)}")


# Get analysis by ID
@app.get("/analysis/{analysis_id}", tags=["History"])
async def get_analysis(analysis_id: UUID):
    """Get a specific analysis by ID"""
    try:
        result = await app.state.database_service.get_analysis(analysis_id)

        if not result:
            raise HTTPException(status_code=404, detail="Analysis not found")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error fetching analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Get recent analyses
@app.get("/history", tags=["History"])
async def get_history(limit: int = 10, offset: int = 0):
    """Get recent analysis history"""
    try:
        results = await app.state.database_service.get_recent_analyses(limit=limit, offset=offset)
        return {"total": len(results), "data": results}

    except Exception as e:
        logfire.error(f"Error fetching history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Get statistics
@app.get("/statistics", tags=["Statistics"])
async def get_statistics():
    """Get analysis statistics"""
    try:
        stats = await app.state.database_service.get_statistics()
        return stats

    except Exception as e:
        logfire.error(f"Error fetching statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Delete analysis
@app.delete("/analysis/{analysis_id}", tags=["History"])
async def delete_analysis(analysis_id: UUID):
    """Delete a specific analysis"""
    try:
        # Get analysis to find image path
        analysis = await app.state.database_service.get_analysis(analysis_id)

        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")

        # Delete from database
        await app.state.database_service.delete_analysis(analysis_id)

        # Note: You might want to also delete from storage
        # Extract path from URL and delete
        # app.state.storage_service.delete_image(path)

        return {"message": "Analysis deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logfire.error(f"Error deleting analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    # Run the server
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
