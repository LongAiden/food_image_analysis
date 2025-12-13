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
from backend.services.image_utils import decode_base64_image, prepare_image, PreparedImage
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

    # Optionally set Telegram webhook automatically if configured
    if settings.telegram_bot_token and settings.telegram_webhook_url:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
                    data={"url": settings.telegram_webhook_url},
                )
                logfire.info("Telegram webhook set", response=resp.json())
        except Exception as exc:
            logfire.warning(f"Failed to set Telegram webhook: {exc}")

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
        raise HTTPException(
            status_code=400, detail="Telegram bot token not configured")

    base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    async with httpx.AsyncClient(timeout=20) as client:
        get_file_resp = await client.get(f"{base_url}/getFile", params={"file_id": file_id})
        if get_file_resp.status_code != 200:
            logfire.error(
                f"Failed to fetch Telegram file metadata: {get_file_resp.text}")
            raise HTTPException(
                status_code=502, detail="Failed to fetch Telegram file metadata")
        file_info = get_file_resp.json().get("result")
        if not file_info or "file_path" not in file_info:
            logfire.error(f"Invalid Telegram file_id: {get_file_resp.text}")
            raise HTTPException(
                status_code=400, detail="Invalid Telegram file_id")

        file_path = file_info["file_path"]
        download_url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
        download_resp = await client.get(download_url)
        if download_resp.status_code != 200:
            logfire.error(f"Failed to download Telegram file : {download_resp.text}")
            raise HTTPException(
                status_code=502, detail="Failed to download Telegram file")

        filename = file_path.rsplit("/", 1)[-1]
        return download_resp.content, filename


async def send_telegram_message(chat_id: int, text: str, settings: Settings) -> None:
    """Send a text message back to a Telegram chat."""
    if not settings.telegram_bot_token:
        return
    base_url = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(
            f"{base_url}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )


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
    file: UploadFile = File(...,
                            description="Food image file (JPEG, PNG, WEBP)"),
    analyzer: GeminiAnalyzer = Depends(get_analyzer),
    storage: StorageService = Depends(get_storage),
    database: DatabaseService = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    """Analyze a food image and return nutritional information."""
    try:
        image_data = await file.read()
        prepared = prepare_image(
            image_data, max_size_mb=settings.max_image_size_mb)

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
        prepared = prepare_image(
            image_data, max_size_mb=settings.max_image_size_mb)

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
    chat_id: int | None = None,
    analyzer: GeminiAnalyzer = Depends(get_analyzer),
    storage: StorageService = Depends(get_storage),
    database: DatabaseService = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    """Analyze an image referenced by a Telegram file_id."""
    nutrition_analysis = None
    try:
        if chat_id:
            await send_telegram_message(chat_id, "Analyzing image...", settings)

        image_data, filename = await fetch_telegram_file(file_id=file_id, settings=settings)
        prepared = prepare_image(
            image_data, max_size_mb=settings.max_image_size_mb)

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
    finally:
        if chat_id:
            try:
                if not nutrition_analysis:
                    return
                reply = (
                    f"Analysis complete:\n"
                    f"Calories: {nutrition_analysis.calories}\n"
                    f"Protein: {nutrition_analysis.protein} g\n"
                    f"Sugar: {nutrition_analysis.sugar} g"
                )
                await send_telegram_message(chat_id, reply, settings)
            except Exception:
                # best-effort; avoid masking original exceptions
                pass


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    update: dict,
    analyzer: GeminiAnalyzer = Depends(get_analyzer),
    storage: StorageService = Depends(get_storage),
    database: DatabaseService = Depends(get_database),
    settings: Settings = Depends(get_settings),
):
    """
    Telegram webhook handler.
    - Expects standard Telegram update payload.
    - Picks the largest photo, analyzes it, stores results, and replies with macros.
    """
    message = update.get("message") or update.get("edited_message")
    if not message:
        return JSONResponse({"ok": True})

    chat_id = message["chat"]["id"]
    if settings.telegram_allowed_chat_ids and chat_id not in settings.telegram_allowed_chat_ids:
        # Ignore unauthorized chats silently
        return JSONResponse({"ok": True})

    caption = message.get("caption") or message.get("text") or ""
    photos = message.get("photo") or []
    if not photos:
        await send_telegram_message(chat_id, "Please send a photo.", settings)
        return JSONResponse({"ok": True})

    file_id = photos[-1]["file_id"]  # largest resolution photo
    nutrition_analysis = None

    try:
        await send_telegram_message(chat_id, "Analyzing image...", settings)

        image_data, filename = await fetch_telegram_file(file_id=file_id, settings=settings)
        prepared = prepare_image(image_data, max_size_mb=settings.max_image_size_mb)

        display_name = caption.strip()[:32] or filename

        nutrition_analysis = await analyzer.analyze_image(
            prepared=prepared, filename=display_name
        )

        storage_result = await storage.upload_image(
            image_data=prepared.image_bytes,
            filename=display_name,
            content_type=prepared.content_type,
        )

        db_record = await database.save_analysis(
            image_path=storage_result["url"], nutrition=nutrition_analysis
        )

        reply = (
            f"Analysis complete:\n"
            f"Calories: {nutrition_analysis.calories}\n"
            f"Protein: {nutrition_analysis.protein} g\n"
            f"Sugar: {nutrition_analysis.sugar} g"
        )
        await send_telegram_message(chat_id, reply, settings)

        return JSONResponse(
            {
                "ok": True,
                "analysis_id": db_record.get("id"),
                "image_url": storage_result["url"],
            }
        )

    except ValueError as exc:
        await send_telegram_message(chat_id, f"Validation error: {exc}", settings)
        return JSONResponse(status_code=400, content={"detail": str(exc)})
    except HTTPException as exc:
        await send_telegram_message(chat_id, f"Error: {exc.detail}", settings)
        raise
    except Exception as exc:
        logfire.error(f"Telegram webhook error: {exc}")
        await send_telegram_message(chat_id, "Analysis failed. Please try again later.", settings)
        return JSONResponse(status_code=500, content={"detail": "Analysis failed"})


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
