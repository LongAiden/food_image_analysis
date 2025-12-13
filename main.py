from contextlib import asynccontextmanager
from uuid import UUID

import logfire
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import httpx

from backend.config import Settings
from backend.models.models import FoodAnalysisRequest, FoodAnalysisResponse
from backend.services.gemini_analyzer import GeminiAnalyzer
from backend.services.image_utils import decode_base64_image, prepare_image
from backend.services.supabase_service import DatabaseService, StorageService

# Load and validate settings once
settings = Settings()

# Configure Logfire early
if settings.logfire_write_token:
    logfire.configure(token=settings.logfire_write_token)
else:
    logfire.configure()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context for app startup and shutdown."""
    logfire.info("Application starting up...")

    app.state.settings = settings
    app.state.gemini_analyzer = GeminiAnalyzer(api_key=settings.google_api_key)
    app.state.storage_service = StorageService(
        url=settings.supabase_url, key=settings.supabase_service_key, bucket_name=settings.supabase_bucket
    )
    app.state.database_service = DatabaseService(
        url=settings.supabase_url, key=settings.supabase_service_key, table_name=settings.supabase_table
    )

    await app.state.storage_service.ensure_bucket_exists()

    yield

    logfire.info("Application shutting down...")


app = FastAPI(
    title="Food Image Analysis API",
    description="API for analyzing food images using Gemini AI to extract nutritional information",
    version="1.0.0",
    lifespan=lifespan,
)

# Instrument FastAPI with Logfire
logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_analyzer(request: Request) -> GeminiAnalyzer:
    return request.app.state.gemini_analyzer


def get_storage(request: Request) -> StorageService:
    return request.app.state.storage_service


def get_database(request: Request) -> DatabaseService:
    return request.app.state.database_service


async def fetch_telegram_file(file_id: str, settings: Settings) -> tuple[bytes, str]:
    """Download a file from Telegram using the bot token."""
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=400, detail="Telegram bot token not configured")

    base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    async with httpx.AsyncClient(timeout=20) as client:
        get_file_resp = await client.get(f"{base_url}/getFile", params={"file_id": file_id})
        if get_file_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch Telegram file metadata")
        file_info = get_file_resp.json().get("result")
        if not file_info or "file_path" not in file_info:
            raise HTTPException(status_code=400, detail="Invalid Telegram file_id")

        file_path = file_info["file_path"]
        download_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
        download_resp = await client.get(download_url)
        if download_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to download Telegram file")

        filename = file_path.rsplit("/", 1)[-1]
        return download_resp.content, filename


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "food-analysis-api", "version": "1.0.0"}


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to Swagger UI."""
    return RedirectResponse(url="/docs")


@app.post("/analyze", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image(
    file: UploadFile = File(..., description="Food image file (JPEG, PNG, WEBP)"),
    analyzer: GeminiAnalyzer = Depends(get_analyzer),
    storage: StorageService = Depends(get_storage),
    database: DatabaseService = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    """Analyze a food image and return nutritional information."""
    try:
        image_data = await file.read()
        prepared = prepare_image(image_data, max_size_mb=settings.max_image_size_mb)

        nutrition_analysis = await analyzer.analyze_image(
            prepared=prepared, filename=file.filename or "upload.jpg"
        )

        storage_result = await storage.upload_image(
            image_data=prepared.image_bytes,
            filename=file.filename,
            content_type=prepared.content_type,
        )

        db_record = await database.save_analysis(
            image_path=storage_result["url"], nutrition=nutrition_analysis
        )

        response = FoodAnalysisResponse(
            analysis_id=UUID(db_record["id"]),
            nutrition=nutrition_analysis,
            image_url=storage_result["url"],
            timestamp=db_record["created_at"],
        )

        return response

    except ValueError as exc:
        logfire.warning(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logfire.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@app.post("/analyze-base64", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image_base64(
    request: FoodAnalysisRequest,
    analyzer: GeminiAnalyzer = Depends(get_analyzer),
    storage: StorageService = Depends(get_storage),
    database: DatabaseService = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    """Analyze a food image from base64 encoded data."""
    try:
        image_data = decode_base64_image(request.image_data)
        prepared = prepare_image(image_data, max_size_mb=settings.max_image_size_mb)

        nutrition_analysis = await analyzer.analyze_image(
            prepared=prepared, filename=request.filename or "image.jpg"
        )

        storage_result = await storage.upload_image(
            image_data=prepared.image_bytes,
            filename=request.filename,
            content_type=prepared.content_type,
        )

        db_record = await database.save_analysis(
            image_path=storage_result["url"], nutrition=nutrition_analysis
        )

        return FoodAnalysisResponse(
            analysis_id=UUID(db_record["id"]),
            nutrition=nutrition_analysis,
            image_url=storage_result["url"],
            timestamp=db_record["created_at"],
        )

    except ValueError as exc:
        logfire.warning(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logfire.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@app.post("/analyze-telegram", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image_telegram(
    file_id: str,
    analyzer: GeminiAnalyzer = Depends(get_analyzer),
    storage: StorageService = Depends(get_storage),
    database: DatabaseService = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    """Analyze an image referenced by a Telegram file_id."""
    try:
        image_data, filename = await fetch_telegram_file(file_id=file_id, settings=settings)
        prepared = prepare_image(image_data, max_size_mb=settings.max_image_size_mb)

        nutrition_analysis = await analyzer.analyze_image(
            prepared=prepared, filename=filename
        )

        storage_result = await storage.upload_image(
            image_data=prepared.image_bytes,
            filename=filename,
            content_type=prepared.content_type,
        )

        db_record = await database.save_analysis(
            image_path=storage_result["url"], nutrition=nutrition_analysis
        )

        return FoodAnalysisResponse(
            analysis_id=UUID(db_record["id"]),
            nutrition=nutrition_analysis,
            image_url=storage_result["url"],
            timestamp=db_record["created_at"],
        )

    except HTTPException:
        raise
    except Exception as exc:
        logfire.error(f"Analysis error (telegram): {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@app.get("/analysis/{analysis_id}", tags=["History"])
async def get_analysis(
    analysis_id: UUID, database: DatabaseService = Depends(get_database)
):
    """Get a specific analysis by ID."""
    result = await database.get_analysis(analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@app.get("/history", tags=["History"])
async def get_history(
    limit: int = 10, offset: int = 0, database: DatabaseService = Depends(get_database)
):
    """Get recent analysis history."""
    results = await database.get_recent_analyses(limit=limit, offset=offset)
    return {"total": len(results), "data": results}


@app.get("/statistics", tags=["Statistics"])
async def get_statistics(database: DatabaseService = Depends(get_database)):
    """Get analysis statistics."""
    return await database.get_statistics()


@app.delete("/analysis/{analysis_id}", tags=["History"])
async def delete_analysis(
    analysis_id: UUID,
    database: DatabaseService = Depends(get_database),
    storage: StorageService = Depends(get_storage),
):
    """Delete a specific analysis (and optionally its image)."""
    analysis = await database.get_analysis(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    await database.delete_analysis(analysis_id)

    # Optional: delete from storage if path can be derived
    image_path = analysis.get("image_path")
    if image_path:
        # best-effort delete
        await storage.delete_image(image_path.split("/")[-1])

    return {"message": "Analysis deleted successfully"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
