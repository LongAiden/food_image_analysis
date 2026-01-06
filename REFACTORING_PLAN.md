# Food Image Analysis - Refactoring Plan

> **Tech Lead Review Date:** 2025-12-29
> **Project:** Food Image Analysis API with Telegram Bot Integration
> **Status:** Action Required

---

## Table of Contents

- [Executive Summary](#executive-summary)
- [Current Architecture Assessment](#current-architecture-assessment)
- [Anti-Patterns Identified](#anti-patterns-identified)
- [Recommended Design Patterns](#recommended-design-patterns)
- [Target Project Structure](#target-project-structure)
- [Implementation Phases](#implementation-phases)
- [Detailed Tasks](#detailed-tasks)
- [Code Examples](#code-examples)
- [Success Metrics](#success-metrics)

---

## Executive Summary

### Current State
- **Strengths:** Clean service layer, type safety with Pydantic, async-first design
- **Weaknesses:** God object in main.py (550 lines), missing implementations, code duplication
- **Blockers:** `/summary` feature cannot be implemented (missing database methods)

### Target State
- Modular architecture with clear separation of concerns
- Repository pattern for data access
- Use Case pattern for business logic
- Command pattern for Telegram commands
- Full test coverage

### Impact on Workflow
Your two main workflows will benefit:
1. **Image Upload → Analysis:** Cleaner, reusable logic across API and Telegram
2. **/summary Command:** Will work properly with weekly statistics (currently broken)

---

## Current Architecture Assessment

### ✅ Strengths

1. **Service-Oriented Architecture**
   - `GeminiAnalyzer` - AI integration
   - `StorageService` - File uploads
   - `DatabaseService` - Data persistence
   - Clear boundaries between services

2. **Type Safety**
   - Pydantic models for validation
   - Type hints throughout
   - Settings-based configuration

3. **Async Operations**
   - Proper async/await usage
   - Thread-safe Supabase operations
   - Non-blocking I/O

4. **Observability**
   - Logfire integration
   - Structured logging
   - Request instrumentation

### ❌ Critical Issues

| Issue | Location | Impact | Priority |
|-------|----------|--------|----------|
| God Object | `main.py:1-550` | Hard to maintain/test | HIGH |
| Missing Methods | `supabase_service.py` | `/summary` broken | CRITICAL |
| Code Duplication | `main.py:375-461` | Maintenance burden | HIGH |
| Unused Config | `backend/storage/configs.py` | Dead code confusion | LOW |
| No Repository Pattern | Throughout | Tight coupling | HIGH |
| No Command Pattern | Telegram handlers | Can't add commands | MEDIUM |

---

## Anti-Patterns Identified

### 1. God Object / Fat Controller

**Location:** `main.py` (550 lines)

**Problem:**
```python
# Single file contains:
- FastAPI app setup (lines 120-136)
- Dependency injection (lines 139-152)
- Telegram file download (lines 155-197)
- Message sending (lines 199-213)
- Update processing (lines 215-307)
- Long polling (lines 309-361)
- API endpoints (lines 363-538)
```

**Why It's Bad:**
- Violates Single Responsibility Principle
- Impossible to test individual components
- Makes code reuse difficult
- Hard to onboard new developers

**Solution:** Split into routers, services, and use cases

---

### 2. Code Duplication

**Location:** `main.py:375-419` and `main.py:421-462`

**Problem:**
```python
# /analyze endpoint (multipart)
async def analyze_food_image(...):
    image_data = await file.read()
    prepared = prepare_image(image_data, ...)
    nutrition_analysis = await analyzer.analyze_image(...)
    storage_result = await storage.upload_image(...)
    db_record = await database.save_analysis(...)
    # ... response construction

# /analyze-base64 endpoint (JSON)
async def analyze_food_image_base64(...):
    image_data = decode_base64_image(...)
    prepared = prepare_image(image_data, ...)  # DUPLICATE
    nutrition_analysis = await analyzer.analyze_image(...)  # DUPLICATE
    storage_result = await storage.upload_image(...)  # DUPLICATE
    db_record = await database.save_analysis(...)  # DUPLICATE
    # ... response construction (DUPLICATE)
```

**Why It's Bad:**
- Bug fixes need to be applied twice
- Easy to forget one location
- Increases testing burden

**Solution:** Extract common logic into a Use Case class

---

### 3. Missing Implementations

**Location:** `backend/services/supabase_service.py`

**Problem:**
```python
# main.py:508
results = await database.get_recent_analyses(limit=limit, offset=offset)
# ❌ Method doesn't exist!

# main.py:515
return await database.get_statistics()
# ❌ Method doesn't exist!
```

**Why It's Bad:**
- API endpoints return 500 errors
- Can't implement `/summary` telegram command
- Breaks user expectations

**Solution:** Implement missing methods (see Phase 1)

---

### 4. Configuration Duplication

**Locations:**
- `backend/config.py` (48 lines) - ✅ USED by application
- `backend/storage/configs.py` (107 lines) - ❌ UNUSED dead code

**Problem:**
```python
# backend/config.py
class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    # ... used everywhere

# backend/storage/configs.py
class SupabaseBucketManager:
    def __init__(self, url: str, key: str):
        self.supabase = create_client(url, key)
    # ... NEVER IMPORTED
```

**Why It's Bad:**
- Confuses developers
- Maintenance overhead
- Suggests incomplete refactoring

**Solution:** Delete `backend/storage/configs.py`

---

### 5. No Repository Pattern

**Problem:** Direct database calls in handlers

**Current Code:**
```python
# main.py:400-402 (API handler)
db_record = await database.save_analysis(
    image_path=storage_result["url"],
    nutrition=nutrition_analysis
)
```

**Why It's Bad:**
- Tight coupling to Supabase
- Hard to mock for testing
- Can't swap databases easily
- Business logic mixed with data access

**Solution:** Create repository interface and implementation

---

### 6. Missing Telegram Command Structure

**Problem:** No way to handle `/summary`, `/start`, `/help` commands

**Current Code:**
```python
# main.py:215-307
async def process_telegram_update(update: dict, ...):
    # Only handles photo messages
    photos = message.get("photo") or []
    if not photos:
        await send_telegram_message(chat_id, "Please send a photo.", settings)
        return
    # No command handling!
```

**Why It's Bad:**
- Can't implement `/summary` command
- All messages treated as photos
- No extensibility for new commands

**Solution:** Implement Command Pattern

---

### 7. No Business Logic Layer

**Problem:** Logic scattered across handlers

**Issues:**
- Can't reuse "analyze image" workflow
- Telegram and API have separate implementations
- No single source of truth for business rules

**Solution:** Create Use Case classes

---

## Recommended Design Patterns

### 1. Repository Pattern

**Purpose:** Abstract data access layer

**Benefits:**
- Easy to mock for testing
- Can swap Supabase for PostgreSQL
- Clean separation of concerns
- Domain-driven design

**Interface:**
```python
class FoodAnalysisRepository(ABC):
    @abstractmethod
    async def save(self, analysis: FoodAnalysis) -> FoodAnalysis:
        """Save a new analysis"""

    @abstractmethod
    async def find_by_id(self, id: UUID) -> Optional[FoodAnalysis]:
        """Find analysis by ID"""

    @abstractmethod
    async def find_recent(self, limit: int, offset: int) -> List[FoodAnalysis]:
        """Get recent analyses with pagination"""

    @abstractmethod
    async def get_weekly_statistics(self, start: datetime, end: datetime) -> Statistics:
        """Get aggregated statistics for date range"""

    @abstractmethod
    async def delete(self, id: UUID) -> bool:
        """Delete an analysis"""
```

**When to Use:** All database operations

---

### 2. Use Case / Interactor Pattern

**Purpose:** Encapsulate business logic

**Benefits:**
- Single Responsibility Principle
- Reusable across entry points (API, Telegram, CLI)
- Easy to test in isolation
- Clear business flow

**Structure:**
```python
class AnalyzeFoodImageUseCase:
    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        storage: StorageService,
        repository: FoodAnalysisRepository,
    ):
        self.analyzer = analyzer
        self.storage = storage
        self.repository = repository

    async def execute(self, input: AnalyzeFoodImageInput) -> AnalyzeFoodImageOutput:
        # 1. Prepare image
        # 2. Analyze with AI
        # 3. Upload to storage
        # 4. Save to database
        # 5. Return result
        pass
```

**When to Use:**
- Analyzing food images
- Getting weekly summaries
- Getting analysis history
- Any multi-step business operation

---

### 3. Command Pattern (Telegram)

**Purpose:** Handle different telegram commands

**Benefits:**
- Easy to add new commands
- Clean separation of command logic
- Testable in isolation
- Follows Open/Closed Principle

**Structure:**
```python
class TelegramCommand(ABC):
    @abstractmethod
    async def execute(self, message: dict, context: BotContext) -> str:
        pass

class SummaryCommand(TelegramCommand):
    async def execute(self, message: dict, context: BotContext) -> str:
        # Get weekly summary
        # Format response
        return formatted_message

class TelegramBotService:
    def register_command(self, name: str, command: TelegramCommand):
        self.commands[name] = command

    async def handle_update(self, update: dict) -> str:
        if text.startswith("/"):
            command_name = text.split()[0][1:]
            return await self.commands[command_name].execute(...)
```

**When to Use:**
- `/summary` command
- `/start` command
- `/help` command
- Any future telegram commands

---

### 4. Factory Pattern

**Purpose:** Centralize service creation

**Benefits:**
- Dependency injection
- Singleton management
- Easy to swap implementations
- Testability

**Structure:**
```python
class ServiceFactory:
    def get_gemini_analyzer(self) -> GeminiAnalyzer:
        pass

    def get_repository(self) -> FoodAnalysisRepository:
        pass

    def get_storage_service(self) -> StorageService:
        pass
```

**When to Use:** Service initialization in lifespan events

---

### 5. Strategy Pattern (Future)

**Purpose:** Support different analysis strategies

**When to Use:**
- Different AI models (Gemini, GPT-4 Vision, Claude)
- Different pricing tiers (free vs premium analysis)
- A/B testing different prompts

**Not Needed Yet:** Keep it simple for now

---

## Target Project Structure

```
food_image_analysis/
├── main.py                              # FastAPI app (50 lines - routing only)
│
├── backend/
│   ├── __init__.py
│   ├── config.py                        # ✅ Keep as-is
│   │
│   ├── domain/                          # NEW: Domain layer
│   │   ├── __init__.py
│   │   ├── entities.py                  # FoodAnalysis, NutritionInfo
│   │   ├── value_objects.py             # HealthScore, CalorieCount
│   │   └── exceptions.py                # Domain-specific exceptions
│   │
│   ├── api/                             # NEW: API layer (DTOs)
│   │   ├── __init__.py
│   │   ├── requests.py                  # FoodAnalysisRequest
│   │   ├── responses.py                 # FoodAnalysisResponse
│   │   └── dependencies.py              # FastAPI dependencies
│   │
│   ├── use_cases/                       # NEW: Business logic
│   │   ├── __init__.py
│   │   ├── analyze_food_image.py        # Main workflow
│   │   ├── get_weekly_summary.py        # For /summary command
│   │   ├── get_analysis_history.py      # For /history endpoint
│   │   └── delete_analysis.py           # For DELETE endpoint
│   │
│   ├── repositories/                    # NEW: Data access abstraction
│   │   ├── __init__.py
│   │   ├── base.py                      # Base repository interface
│   │   ├── food_analysis_repository.py  # Abstract interface
│   │   └── supabase_food_repository.py  # Supabase implementation
│   │
│   ├── services/                        # External integrations
│   │   ├── __init__.py
│   │   ├── gemini_analyzer.py           # ✅ Keep
│   │   ├── image_utils.py               # ✅ Keep
│   │   ├── storage_service.py           # Renamed from supabase_service.py
│   │   └── telegram_bot_service.py      # NEW: Telegram abstraction
│   │
│   ├── routes/                          # NEW: FastAPI routers
│   │   ├── __init__.py
│   │   ├── analysis.py                  # POST /analyze, /analyze-base64
│   │   ├── history.py                   # GET /history, /statistics, /analysis/{id}
│   │   ├── telegram.py                  # POST /telegram/webhook
│   │   └── health.py                    # GET /health
│   │
│   └── infrastructure/                  # NEW: External implementations
│       ├── __init__.py
│       └── supabase/
│           ├── __init__.py
│           ├── client.py                # Supabase client wrapper
│           └── repositories.py          # Repository implementations
│
├── tests/                               # NEW: Test suite
│   ├── __init__.py
│   ├── unit/
│   │   ├── test_use_cases.py
│   │   ├── test_repositories.py
│   │   └── test_services.py
│   ├── integration/
│   │   ├── test_api.py
│   │   └── test_telegram.py
│   └── e2e/
│       └── test_workflows.py
│
├── requirements.txt                     # ✅ Keep
├── .env.example                         # ✅ Keep
├── .gitignore                           # ✅ Keep
├── README.md                            # ✅ Keep
├── TELEGRAM_SETUP.md                    # ✅ Keep
└── REFACTORING_PLAN.md                  # This file
```

### Files to DELETE
- ❌ `backend/storage/configs.py` (unused)
- ❌ `backend/models/models.py` (split into api/requests.py, api/responses.py, domain/entities.py)

### Files to RENAME
- `backend/services/supabase_service.py` → Split into:
  - `backend/services/storage_service.py` (StorageService class)
  - `backend/repositories/supabase_food_repository.py` (DatabaseService → Repository)

---

## Implementation Phases

### Phase 1: Critical Fixes (Week 1)
**Goal:** Unblock `/summary` feature and fix broken endpoints

**Duration:** 2-3 days

**Tasks:**
1. Implement missing database methods
2. Delete unused configuration file
3. Extract duplicate code into shared function

**Deliverables:**
- `/history` endpoint works
- `/statistics` endpoint works
- Ready to implement `/summary` telegram command

---

### Phase 2: Repository Pattern (Week 2)
**Goal:** Abstract data access layer

**Duration:** 3-4 days

**Tasks:**
1. Create repository interface
2. Implement Supabase repository
3. Replace direct database calls
4. Add repository tests

**Deliverables:**
- All database access goes through repository
- Easier to test
- Ready to swap databases if needed

---

### Phase 3: Use Case Layer (Week 2-3)
**Goal:** Encapsulate business logic

**Duration:** 4-5 days

**Tasks:**
1. Create AnalyzeFoodImageUseCase
2. Create GetWeeklySummaryUseCase
3. Create GetAnalysisHistoryUseCase
4. Update API handlers to use use cases
5. Add use case tests

**Deliverables:**
- Business logic reusable across entry points
- No code duplication
- Clear business flow

---

### Phase 4: Telegram Command Pattern (Week 3)
**Goal:** Support telegram commands

**Duration:** 2-3 days

**Tasks:**
1. Create TelegramBotService
2. Implement Command pattern
3. Create SummaryCommand
4. Create PhotoAnalysisCommand
5. Update telegram webhook handler

**Deliverables:**
- `/summary` command works
- Easy to add new commands
- Clean telegram logic

---

### Phase 5: Structure Cleanup (Week 4)
**Goal:** Modular architecture

**Duration:** 3-4 days

**Tasks:**
1. Split main.py into routers
2. Create domain entities
3. Separate DTOs from domain models
4. Move infrastructure code
5. Update imports

**Deliverables:**
- main.py under 100 lines
- Clear layer boundaries
- Easy to navigate codebase

---

### Phase 6: Testing & Documentation (Week 4-5)
**Goal:** Ensure quality and maintainability

**Duration:** 3-4 days

**Tasks:**
1. Write unit tests for use cases
2. Write integration tests for API
3. Write e2e tests for workflows
4. Update README with new structure
5. Add API documentation

**Deliverables:**
- 80%+ test coverage
- Comprehensive documentation
- CI/CD ready

---

## Detailed Tasks

### PHASE 1: Critical Fixes

#### Task 1.1: Implement `get_recent_analyses()`
**File:** `backend/services/supabase_service.py`
**Priority:** CRITICAL
**Estimated Time:** 30 minutes

**Current State:**
```python
# Method is called but doesn't exist
# main.py:508
results = await database.get_recent_analyses(limit=limit, offset=offset)
```

**Implementation:**
```python
async def get_recent_analyses(self, limit: int = 10, offset: int = 0) -> List[dict]:
    """Get recent analyses with pagination."""
    response = await self._run_with_retry(
        lambda: self.client.table(self.table_name)
        .select("*")
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return response.data
```

**Acceptance Criteria:**
- [ ] Method added to DatabaseService class
- [ ] Returns list of analysis records
- [ ] Supports pagination with limit and offset
- [ ] Orders by created_at descending
- [ ] GET /history endpoint returns 200 status

**Testing:**
```bash
# Test the endpoint
curl http://localhost:8000/history?limit=5&offset=0
```

---

#### Task 1.2: Implement `get_statistics()`
**File:** `backend/services/supabase_service.py`
**Priority:** CRITICAL
**Estimated Time:** 45 minutes

**Current State:**
```python
# Method is called but doesn't exist
# main.py:515
return await database.get_statistics()
```

**Implementation:**
```python
async def get_statistics(self, days: int = 7) -> dict:
    """Get nutrition statistics for the last N days."""
    from datetime import datetime, timedelta

    start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

    response = await self._run_with_retry(
        lambda: self.client.table(self.table_name)
        .select("*")
        .gte("created_at", start_date)
        .execute()
    )

    analyses = response.data
    if not analyses:
        return {
            "period_days": days,
            "total_meals": 0,
            "total_calories": 0,
            "avg_calories": 0,
            "total_protein": 0,
            "avg_protein": 0,
            "total_sugar": 0,
            "avg_sugar": 0,
            "total_carbs": 0,
            "avg_carbs": 0,
            "total_fat": 0,
            "avg_fat": 0,
            "total_fiber": 0,
            "avg_fiber": 0,
            "avg_health_score": 0
        }

    total_meals = len(analyses)
    total_calories = sum(a["calories"] for a in analyses)
    total_protein = sum(a["protein"] for a in analyses)
    total_sugar = sum(a["sugar"] for a in analyses)
    total_carbs = sum(a["carbs"] for a in analyses)
    total_fat = sum(a["fat"] for a in analyses)
    total_fiber = sum(a["fiber"] for a in analyses)
    avg_health_score = sum(a.get("health_score", 0) for a in analyses) / total_meals

    return {
        "period_days": days,
        "total_meals": total_meals,
        "total_calories": round(total_calories, 1),
        "avg_calories": round(total_calories / total_meals, 1),
        "total_protein": round(total_protein, 1),
        "avg_protein": round(total_protein / total_meals, 1),
        "total_sugar": round(total_sugar, 1),
        "avg_sugar": round(total_sugar / total_meals, 1),
        "total_carbs": round(total_carbs, 1),
        "avg_carbs": round(total_carbs / total_meals, 1),
        "total_fat": round(total_fat, 1),
        "avg_fat": round(total_fat / total_meals, 1),
        "total_fiber": round(total_fiber, 1),
        "avg_fiber": round(total_fiber / total_meals, 1),
        "avg_health_score": round(avg_health_score, 1)
    }
```

**Acceptance Criteria:**
- [ ] Method added to DatabaseService class
- [ ] Returns statistics for last 7 days by default
- [ ] Supports custom day range parameter
- [ ] Calculates totals and averages for all nutrients
- [ ] Handles empty result set gracefully
- [ ] GET /statistics endpoint returns 200 status

**Testing:**
```bash
# Test the endpoint
curl http://localhost:8000/statistics
```

---

#### Task 1.3: Delete Unused Config File
**File:** `backend/storage/configs.py`
**Priority:** LOW
**Estimated Time:** 5 minutes

**Action:**
```bash
rm backend/storage/configs.py
```

**Verify:**
```bash
# Search for any imports (should find none)
grep -r "from backend.storage.configs" .
grep -r "import backend.storage.configs" .
```

**Acceptance Criteria:**
- [ ] File deleted
- [ ] No import references exist
- [ ] Application still runs successfully

---

#### Task 1.4: Extract Common Analysis Logic
**File:** Create `backend/services/analysis_service.py`
**Priority:** HIGH
**Estimated Time:** 1 hour

**Current Problem:**
```python
# main.py:375-419 - /analyze endpoint
# main.py:421-462 - /analyze-base64 endpoint
# 80% duplicate code between these two endpoints
```

**New Service:**
```python
# backend/services/analysis_service.py
from dataclasses import dataclass
from uuid import UUID
from datetime import datetime

from backend.models.models import NutritionAnalysis
from backend.services.gemini_analyzer import GeminiAnalyzer
from backend.services.image_utils import prepare_image
from backend.services.supabase_service import StorageService, DatabaseService


@dataclass
class AnalysisResult:
    """Result of food image analysis"""
    analysis_id: UUID
    nutrition: NutritionAnalysis
    image_url: str
    timestamp: datetime


class AnalysisService:
    """Service for analyzing food images (shared logic)"""

    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        storage: StorageService,
        database: DatabaseService,
        max_image_size_mb: float
    ):
        self.analyzer = analyzer
        self.storage = storage
        self.database = database
        self.max_image_size_mb = max_image_size_mb

    async def analyze_and_store(
        self,
        image_data: bytes,
        filename: str
    ) -> AnalysisResult:
        """
        Analyze a food image and store results.

        This is the common logic used by both:
        - POST /analyze (multipart upload)
        - POST /analyze-base64 (JSON upload)
        - Telegram webhook handler
        """
        # 1. Prepare and validate image
        prepared = prepare_image(
            image_data,
            max_size_mb=self.max_image_size_mb
        )

        # 2. Analyze with Gemini AI
        nutrition_analysis = await self.analyzer.analyze_image(
            prepared=prepared,
            filename=filename
        )

        # 3. Upload to Supabase Storage
        storage_result = await self.storage.upload_image(
            image_data=prepared.image_bytes,
            filename=filename,
            content_type=prepared.content_type,
        )

        # 4. Save to Supabase Database
        db_record = await self.database.save_analysis(
            image_path=storage_result["url"],
            nutrition=nutrition_analysis
        )

        # 5. Return structured result
        return AnalysisResult(
            analysis_id=UUID(db_record["id"]),
            nutrition=nutrition_analysis,
            image_url=storage_result["url"],
            timestamp=db_record["created_at"]
        )
```

**Update main.py:**
```python
# Add to imports
from backend.services.analysis_service import AnalysisService, AnalysisResult

# Add to lifespan
app.state.analysis_service = AnalysisService(
    analyzer=app.state.gemini_analyzer,
    storage=app.state.storage_service,
    database=app.state.database_service,
    max_image_size_mb=settings.max_image_size_mb
)

# Add dependency
def get_analysis_service(request: Request) -> AnalysisService:
    return request.app.state.analysis_service

# Update /analyze endpoint
@app.post("/analyze", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image(
    file: UploadFile = File(...),
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Analyze a food image and return nutritional information."""
    try:
        image_data = await file.read()
        result = await analysis_service.analyze_and_store(
            image_data=image_data,
            filename=file.filename or "upload.jpg"
        )

        return FoodAnalysisResponse(
            analysis_id=result.analysis_id,
            nutrition=result.nutrition,
            image_url=result.image_url,
            timestamp=result.timestamp,
        )
    except ValueError as exc:
        logfire.warning(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logfire.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

# Update /analyze-base64 endpoint
@app.post("/analyze-base64", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image_base64(
    request: FoodAnalysisRequest,
    analysis_service: AnalysisService = Depends(get_analysis_service),
):
    """Analyze a food image from base64 encoded data."""
    try:
        image_data = decode_base64_image(request.image_data)
        result = await analysis_service.analyze_and_store(
            image_data=image_data,
            filename=request.filename or "image.jpg"
        )

        return FoodAnalysisResponse(
            analysis_id=result.analysis_id,
            nutrition=result.nutrition,
            image_url=result.image_url,
            timestamp=result.timestamp,
        )
    except ValueError as exc:
        logfire.warning(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logfire.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
```

**Also Update Telegram Handler:**
```python
# main.py: process_telegram_update function
# Replace lines 255-271 with:
result = await analysis_service.analyze_and_store(
    image_data=image_data,
    filename=display_name
)

# Update reply construction (lines 275-288)
reply = (
    f"Analysis complete:\n"
    f"\n"
    f"- Food: {result.nutrition.food_name}\n"
    f"- Calories: {result.nutrition.calories}\n"
    f"- Protein: {result.nutrition.protein} g\n"
    f"- Sugar: {result.nutrition.sugar} g\n"
    f"- Fat: {result.nutrition.fat} g\n"
    f"- Fiber: {result.nutrition.fiber} g\n"
    f"- Carbs: {result.nutrition.carbs} g\n"
    f"\n"
    f"Health Score: {result.nutrition.health_score}/100"
)

# Update return statement (line 290-293)
return True, {
    "analysis_id": str(result.analysis_id),
    "image_url": result.image_url,
}, 200
```

**Acceptance Criteria:**
- [ ] New AnalysisService class created
- [ ] Both /analyze endpoints use the service
- [ ] Telegram handler uses the service
- [ ] No code duplication
- [ ] All three entry points work correctly

**Testing:**
```bash
# Test multipart upload
curl -X POST http://localhost:8000/analyze \
  -F "file=@test_image.jpg"

# Test base64 upload
curl -X POST http://localhost:8000/analyze-base64 \
  -H "Content-Type: application/json" \
  -d '{"image_data": "..."}'

# Test telegram (send photo to bot)
```

---

### PHASE 2: Repository Pattern

#### Task 2.1: Create Repository Interface
**File:** Create `backend/repositories/food_analysis_repository.py`
**Priority:** HIGH
**Estimated Time:** 1 hour

**Implementation:**
```python
# backend/repositories/food_analysis_repository.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from backend.domain.entities import FoodAnalysis
from backend.domain.value_objects import WeeklyStatistics


class FoodAnalysisRepository(ABC):
    """Abstract repository for food analysis persistence"""

    @abstractmethod
    async def save(self, analysis: FoodAnalysis) -> FoodAnalysis:
        """
        Save a new food analysis.

        Args:
            analysis: FoodAnalysis entity to save

        Returns:
            Saved FoodAnalysis with generated ID and timestamp
        """
        pass

    @abstractmethod
    async def find_by_id(self, analysis_id: UUID) -> Optional[FoodAnalysis]:
        """
        Find an analysis by its ID.

        Args:
            analysis_id: UUID of the analysis

        Returns:
            FoodAnalysis if found, None otherwise
        """
        pass

    @abstractmethod
    async def find_recent(self, limit: int = 10, offset: int = 0) -> List[FoodAnalysis]:
        """
        Find recent analyses with pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of FoodAnalysis ordered by created_at descending
        """
        pass

    @abstractmethod
    async def find_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[FoodAnalysis]:
        """
        Find analyses within a date range.

        Args:
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)

        Returns:
            List of FoodAnalysis within the date range
        """
        pass

    @abstractmethod
    async def get_statistics(self, days: int = 7) -> WeeklyStatistics:
        """
        Get aggregated statistics for the last N days.

        Args:
            days: Number of days to include (default 7)

        Returns:
            WeeklyStatistics with aggregated nutrition data
        """
        pass

    @abstractmethod
    async def delete(self, analysis_id: UUID) -> bool:
        """
        Delete an analysis by ID.

        Args:
            analysis_id: UUID of the analysis to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def count_total(self) -> int:
        """
        Get total count of all analyses.

        Returns:
            Total number of analyses in the database
        """
        pass
```

**Also Create:**
```python
# backend/repositories/__init__.py
from .food_analysis_repository import FoodAnalysisRepository

__all__ = ["FoodAnalysisRepository"]
```

**Acceptance Criteria:**
- [ ] Abstract base class created
- [ ] All methods have clear docstrings
- [ ] Type hints for all parameters and returns
- [ ] Follows repository pattern best practices

---

#### Task 2.2: Create Domain Entities
**File:** Create `backend/domain/entities.py`
**Priority:** HIGH
**Estimated Time:** 45 minutes

**Implementation:**
```python
# backend/domain/entities.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class NutritionInfo:
    """Value object for nutrition information"""
    food_name: str
    calories: float
    sugar: float
    protein: float
    carbs: float
    fat: float
    fiber: float
    health_score: Optional[int] = None
    others: str = ""

    def __post_init__(self):
        """Validate nutrition values"""
        if self.calories < 0:
            raise ValueError("Calories cannot be negative")
        if self.protein < 0:
            raise ValueError("Protein cannot be negative")
        if self.health_score is not None and not 0 <= self.health_score <= 100:
            raise ValueError("Health score must be between 0 and 100")


@dataclass
class FoodAnalysis:
    """Domain entity for food analysis"""
    nutrition: NutritionInfo
    image_url: str
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    created_at: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "id": str(self.id),
            "food_name": self.nutrition.food_name,
            "calories": self.nutrition.calories,
            "sugar": self.nutrition.sugar,
            "protein": self.nutrition.protein,
            "carbs": self.nutrition.carbs,
            "fat": self.nutrition.fat,
            "fiber": self.nutrition.fiber,
            "health_score": self.nutrition.health_score,
            "others": self.nutrition.others,
            "image_url": self.image_url,
            "timestamp": self.timestamp.isoformat(),
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FoodAnalysis":
        """Create from dictionary"""
        nutrition = NutritionInfo(
            food_name=data["food_name"],
            calories=data["calories"],
            sugar=data["sugar"],
            protein=data["protein"],
            carbs=data["carbs"],
            fat=data["fat"],
            fiber=data["fiber"],
            health_score=data.get("health_score"),
            others=data.get("others", ""),
        )

        return cls(
            id=UUID(data["id"]) if isinstance(data["id"], str) else data["id"],
            nutrition=nutrition,
            image_url=data["image_path"],  # Note: DB uses "image_path"
            timestamp=datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00")),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            user_id=data.get("user_id"),
        )
```

**Also Create:**
```python
# backend/domain/value_objects.py
from dataclasses import dataclass


@dataclass
class WeeklyStatistics:
    """Value object for weekly nutrition statistics"""
    period_days: int
    total_meals: int
    total_calories: float
    avg_calories: float
    total_protein: float
    avg_protein: float
    total_sugar: float
    avg_sugar: float
    total_carbs: float
    avg_carbs: float
    total_fat: float
    avg_fat: float
    total_fiber: float
    avg_fiber: float
    avg_health_score: float

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "period_days": self.period_days,
            "total_meals": self.total_meals,
            "total_calories": round(self.total_calories, 1),
            "avg_calories": round(self.avg_calories, 1),
            "total_protein": round(self.total_protein, 1),
            "avg_protein": round(self.avg_protein, 1),
            "total_sugar": round(self.total_sugar, 1),
            "avg_sugar": round(self.avg_sugar, 1),
            "total_carbs": round(self.total_carbs, 1),
            "avg_carbs": round(self.avg_carbs, 1),
            "total_fat": round(self.total_fat, 1),
            "avg_fat": round(self.avg_fat, 1),
            "total_fiber": round(self.total_fiber, 1),
            "avg_fiber": round(self.avg_fiber, 1),
            "avg_health_score": round(self.avg_health_score, 1),
        }


@dataclass
class HealthScore:
    """Value object for health score (0-100)"""
    value: int

    def __post_init__(self):
        if not 0 <= self.value <= 100:
            raise ValueError("Health score must be between 0 and 100")

    def is_healthy(self) -> bool:
        """Check if score indicates healthy food"""
        return self.value >= 70

    def category(self) -> str:
        """Get health category"""
        if self.value >= 80:
            return "Excellent"
        elif self.value >= 60:
            return "Good"
        elif self.value >= 40:
            return "Fair"
        else:
            return "Poor"
```

**Acceptance Criteria:**
- [ ] Domain entities separated from DTOs
- [ ] Validation in entity constructors
- [ ] Conversion methods (to_dict, from_dict)
- [ ] No framework dependencies (pure Python)

---

#### Task 2.3: Implement Supabase Repository
**File:** Create `backend/repositories/supabase_food_repository.py`
**Priority:** HIGH
**Estimated Time:** 2 hours

**Implementation:**
```python
# backend/repositories/supabase_food_repository.py
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

import logfire
from anyio import to_thread
from supabase import Client, create_client

from backend.domain.entities import FoodAnalysis, NutritionInfo
from backend.domain.value_objects import WeeklyStatistics
from backend.repositories.food_analysis_repository import FoodAnalysisRepository


class SupabaseFoodAnalysisRepository(FoodAnalysisRepository):
    """Supabase implementation of FoodAnalysisRepository"""

    def __init__(self, url: str, key: str, table_name: str = "food_analyses"):
        if not url or not key:
            raise ValueError("Supabase URL and key are required")

        self.client: Client = create_client(url, key)
        self.table_name = table_name
        logfire.info("Supabase repository initialized", table=table_name)

    async def _run_with_retry(self, func, retries: int = 2):
        """Execute Supabase operation with retry logic"""
        delay = 0.2
        last_exc = None
        for _ in range(retries + 1):
            try:
                return await to_thread.run_sync(func)
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(delay)
                delay *= 2
        raise last_exc

    async def save(self, analysis: FoodAnalysis) -> FoodAnalysis:
        """Save a food analysis to Supabase"""
        record = {
            "id": str(analysis.id),
            "image_path": analysis.image_url,
            "food_name": analysis.nutrition.food_name,
            "calories": analysis.nutrition.calories,
            "sugar": analysis.nutrition.sugar,
            "protein": analysis.nutrition.protein,
            "carbs": analysis.nutrition.carbs,
            "fat": analysis.nutrition.fat,
            "fiber": analysis.nutrition.fiber,
            "health_score": analysis.nutrition.health_score,
            "others": analysis.nutrition.others,
            "timestamp": analysis.timestamp.isoformat(),
            "raw_result": {
                "food_name": analysis.nutrition.food_name,
                "calories": analysis.nutrition.calories,
                "sugar": analysis.nutrition.sugar,
                "protein": analysis.nutrition.protein,
                "carbs": analysis.nutrition.carbs,
                "fat": analysis.nutrition.fat,
                "fiber": analysis.nutrition.fiber,
                "health_score": analysis.nutrition.health_score,
                "others": analysis.nutrition.others,
            }
        }

        response = await self._run_with_retry(
            lambda: self.client.table(self.table_name).insert(record).execute()
        )

        if not response.data:
            raise RuntimeError("Failed to save analysis")

        logfire.info("Analysis saved", id=str(analysis.id))
        return FoodAnalysis.from_dict(response.data[0])

    async def find_by_id(self, analysis_id: UUID) -> Optional[FoodAnalysis]:
        """Find an analysis by ID"""
        try:
            response = await self._run_with_retry(
                lambda: self.client.table(self.table_name)
                .select("*")
                .eq("id", str(analysis_id))
                .execute()
            )

            if not response.data:
                return None

            return FoodAnalysis.from_dict(response.data[0])

        except Exception as exc:
            logfire.error(f"Error finding analysis {analysis_id}: {exc}")
            return None

    async def find_recent(self, limit: int = 10, offset: int = 0) -> List[FoodAnalysis]:
        """Find recent analyses with pagination"""
        response = await self._run_with_retry(
            lambda: self.client.table(self.table_name)
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return [FoodAnalysis.from_dict(row) for row in response.data]

    async def find_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[FoodAnalysis]:
        """Find analyses within date range"""
        response = await self._run_with_retry(
            lambda: self.client.table(self.table_name)
            .select("*")
            .gte("created_at", start_date.isoformat())
            .lte("created_at", end_date.isoformat())
            .order("created_at", desc=True)
            .execute()
        )

        return [FoodAnalysis.from_dict(row) for row in response.data]

    async def get_statistics(self, days: int = 7) -> WeeklyStatistics:
        """Get aggregated statistics"""
        start_date = datetime.utcnow() - timedelta(days=days)
        analyses = await self.find_by_date_range(start_date, datetime.utcnow())

        if not analyses:
            return WeeklyStatistics(
                period_days=days,
                total_meals=0,
                total_calories=0,
                avg_calories=0,
                total_protein=0,
                avg_protein=0,
                total_sugar=0,
                avg_sugar=0,
                total_carbs=0,
                avg_carbs=0,
                total_fat=0,
                avg_fat=0,
                total_fiber=0,
                avg_fiber=0,
                avg_health_score=0
            )

        total_meals = len(analyses)
        total_calories = sum(a.nutrition.calories for a in analyses)
        total_protein = sum(a.nutrition.protein for a in analyses)
        total_sugar = sum(a.nutrition.sugar for a in analyses)
        total_carbs = sum(a.nutrition.carbs for a in analyses)
        total_fat = sum(a.nutrition.fat for a in analyses)
        total_fiber = sum(a.nutrition.fiber for a in analyses)
        avg_health = sum(
            a.nutrition.health_score or 0 for a in analyses
        ) / total_meals

        return WeeklyStatistics(
            period_days=days,
            total_meals=total_meals,
            total_calories=total_calories,
            avg_calories=total_calories / total_meals,
            total_protein=total_protein,
            avg_protein=total_protein / total_meals,
            total_sugar=total_sugar,
            avg_sugar=total_sugar / total_meals,
            total_carbs=total_carbs,
            avg_carbs=total_carbs / total_meals,
            total_fat=total_fat,
            avg_fat=total_fat / total_meals,
            total_fiber=total_fiber,
            avg_fiber=total_fiber / total_meals,
            avg_health_score=avg_health
        )

    async def delete(self, analysis_id: UUID) -> bool:
        """Delete an analysis"""
        try:
            await self._run_with_retry(
                lambda: self.client.table(self.table_name)
                .delete()
                .eq("id", str(analysis_id))
                .execute()
            )
            logfire.info("Analysis deleted", id=str(analysis_id))
            return True
        except Exception as exc:
            logfire.error(f"Error deleting analysis {analysis_id}: {exc}")
            return False

    async def count_total(self) -> int:
        """Get total count of analyses"""
        response = await self._run_with_retry(
            lambda: self.client.table(self.table_name)
            .select("id", count="exact")
            .execute()
        )
        return response.count or 0
```

**Acceptance Criteria:**
- [ ] Implements all repository interface methods
- [ ] Uses async/await properly
- [ ] Has retry logic for transient failures
- [ ] Converts between domain entities and database records
- [ ] Comprehensive error handling and logging

---

#### Task 2.4: Replace Direct Database Calls
**File:** `main.py`, `backend/services/analysis_service.py`
**Priority:** HIGH
**Estimated Time:** 1 hour

**Changes Required:**

1. Update lifespan in main.py:
```python
# Replace DatabaseService with Repository
app.state.food_repository = SupabaseFoodAnalysisRepository(
    url=settings.supabase_url,
    key=settings.supabase_service_key,
    table_name=settings.supabase_table
)

# Keep DatabaseService for now (gradual migration)
app.state.database_service = DatabaseService(...)
```

2. Update dependencies:
```python
def get_food_repository(request: Request) -> FoodAnalysisRepository:
    return request.app.state.food_repository
```

3. Update AnalysisService to use repository:
```python
class AnalysisService:
    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        storage: StorageService,
        repository: FoodAnalysisRepository,  # Changed from DatabaseService
        max_image_size_mb: float
    ):
        self.analyzer = analyzer
        self.storage = storage
        self.repository = repository
        self.max_image_size_mb = max_image_size_mb

    async def analyze_and_store(
        self,
        image_data: bytes,
        filename: str
    ) -> FoodAnalysis:  # Changed return type
        prepared = prepare_image(image_data, self.max_image_size_mb)
        nutrition = await self.analyzer.analyze_image(prepared, filename)
        storage_result = await self.storage.upload_image(...)

        # Create domain entity
        analysis = FoodAnalysis(
            nutrition=NutritionInfo(
                food_name=nutrition.food_name,
                calories=nutrition.calories,
                # ... other fields
            ),
            image_url=storage_result["url"]
        )

        # Save via repository
        saved = await self.repository.save(analysis)
        return saved
```

4. Update endpoints to use repository:
```python
@app.get("/history", tags=["History"])
async def get_history(
    limit: int = 10,
    offset: int = 0,
    repository: FoodAnalysisRepository = Depends(get_food_repository)
):
    analyses = await repository.find_recent(limit=limit, offset=offset)
    return {
        "total": len(analyses),
        "data": [a.to_dict() for a in analyses]
    }

@app.get("/statistics", tags=["Statistics"])
async def get_statistics(
    repository: FoodAnalysisRepository = Depends(get_food_repository)
):
    stats = await repository.get_statistics(days=7)
    return stats.to_dict()
```

**Acceptance Criteria:**
- [ ] All endpoints use repository instead of direct DB service
- [ ] AnalysisService uses repository
- [ ] Domain entities used throughout
- [ ] All tests pass
- [ ] No breaking changes to API responses

---

### PHASE 3: Use Case Layer

#### Task 3.1: Create AnalyzeFoodImageUseCase
**File:** Create `backend/use_cases/analyze_food_image.py`
**Priority:** HIGH
**Estimated Time:** 1.5 hours

**Implementation:**
```python
# backend/use_cases/analyze_food_image.py
from dataclasses import dataclass

import logfire

from backend.domain.entities import FoodAnalysis, NutritionInfo
from backend.repositories.food_analysis_repository import FoodAnalysisRepository
from backend.services.gemini_analyzer import GeminiAnalyzer
from backend.services.image_utils import prepare_image
from backend.services.supabase_service import StorageService


@dataclass
class AnalyzeFoodImageInput:
    """Input for AnalyzeFoodImageUseCase"""
    image_data: bytes
    filename: str
    user_id: str | None = None


@dataclass
class AnalyzeFoodImageOutput:
    """Output from AnalyzeFoodImageUseCase"""
    analysis: FoodAnalysis


class AnalyzeFoodImageUseCase:
    """
    Use case for analyzing food images and storing results.

    This encapsulates the core business logic for:
    1. Validating and preparing the image
    2. Analyzing with AI
    3. Uploading to storage
    4. Persisting to database

    Can be used from:
    - REST API endpoints
    - Telegram bot
    - CLI tools
    - Background jobs
    """

    def __init__(
        self,
        analyzer: GeminiAnalyzer,
        storage: StorageService,
        repository: FoodAnalysisRepository,
        max_image_size_mb: float = 10.0
    ):
        self.analyzer = analyzer
        self.storage = storage
        self.repository = repository
        self.max_image_size_mb = max_image_size_mb

    async def execute(self, input: AnalyzeFoodImageInput) -> AnalyzeFoodImageOutput:
        """
        Execute the food image analysis workflow.

        Args:
            input: AnalyzeFoodImageInput with image data and metadata

        Returns:
            AnalyzeFoodImageOutput with complete analysis

        Raises:
            ValueError: If image is invalid or too large
            RuntimeError: If analysis or storage fails
        """
        logfire.info(
            "Starting food image analysis",
            filename=input.filename,
            user_id=input.user_id
        )

        # Step 1: Prepare and validate image
        logfire.debug("Preparing image")
        prepared = prepare_image(
            input.image_data,
            max_size_mb=self.max_image_size_mb
        )

        # Step 2: Analyze with Gemini AI
        logfire.debug("Analyzing with Gemini AI")
        nutrition_pydantic = await self.analyzer.analyze_image(
            prepared=prepared,
            filename=input.filename
        )

        # Step 3: Upload to storage
        logfire.debug("Uploading to storage")
        storage_result = await self.storage.upload_image(
            image_data=prepared.image_bytes,
            filename=input.filename,
            content_type=prepared.content_type,
        )

        # Step 4: Create domain entity
        nutrition = NutritionInfo(
            food_name=nutrition_pydantic.food_name,
            calories=nutrition_pydantic.calories,
            sugar=nutrition_pydantic.sugar,
            protein=nutrition_pydantic.protein,
            carbs=nutrition_pydantic.carbs,
            fat=nutrition_pydantic.fat,
            fiber=nutrition_pydantic.fiber,
            health_score=nutrition_pydantic.health_score,
            others=nutrition_pydantic.others,
        )

        analysis = FoodAnalysis(
            nutrition=nutrition,
            image_url=storage_result["url"],
            user_id=input.user_id
        )

        # Step 5: Persist to database
        logfire.debug("Saving to database")
        saved_analysis = await self.repository.save(analysis)

        logfire.info(
            "Food image analysis completed",
            analysis_id=str(saved_analysis.id),
            food_name=saved_analysis.nutrition.food_name,
            calories=saved_analysis.nutrition.calories
        )

        return AnalyzeFoodImageOutput(analysis=saved_analysis)
```

**Update API endpoints:**
```python
# main.py or backend/routes/analysis.py
@app.post("/analyze", response_model=FoodAnalysisResponse, tags=["Analysis"])
async def analyze_food_image(
    file: UploadFile = File(...),
    use_case: AnalyzeFoodImageUseCase = Depends(get_analyze_use_case),
):
    """Analyze a food image and return nutritional information."""
    try:
        image_data = await file.read()
        input = AnalyzeFoodImageInput(
            image_data=image_data,
            filename=file.filename or "upload.jpg"
        )

        output = await use_case.execute(input)

        return FoodAnalysisResponse(
            analysis_id=output.analysis.id,
            nutrition=NutritionAnalysis(
                food_name=output.analysis.nutrition.food_name,
                calories=output.analysis.nutrition.calories,
                # ... map fields
            ),
            image_url=output.analysis.image_url,
            timestamp=output.analysis.timestamp,
        )

    except ValueError as exc:
        logfire.warning(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logfire.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
```

**Acceptance Criteria:**
- [ ] Use case class created with clear input/output
- [ ] All business logic encapsulated
- [ ] Comprehensive logging
- [ ] Error handling
- [ ] API endpoints updated to use it
- [ ] Works with both /analyze and /analyze-base64

---

#### Task 3.2: Create GetWeeklySummaryUseCase
**File:** Create `backend/use_cases/get_weekly_summary.py`
**Priority:** HIGH (needed for /summary command)
**Estimated Time:** 45 minutes

**Implementation:**
```python
# backend/use_cases/get_weekly_summary.py
from dataclasses import dataclass

import logfire

from backend.domain.value_objects import WeeklyStatistics
from backend.repositories.food_analysis_repository import FoodAnalysisRepository


@dataclass
class GetWeeklySummaryInput:
    """Input for GetWeeklySummaryUseCase"""
    days: int = 7
    user_id: str | None = None  # For future multi-user support


@dataclass
class GetWeeklySummaryOutput:
    """Output from GetWeeklySummaryUseCase"""
    statistics: WeeklyStatistics

    def format_telegram_message(self) -> str:
        """Format statistics as Telegram message"""
        stats = self.statistics

        if stats.total_meals == 0:
            return (
                "📊 Your Weekly Summary\n\n"
                "No meals recorded in the last 7 days.\n"
                "Send me a photo of your food to get started!"
            )

        return (
            f"📊 Your Weekly Summary ({stats.period_days} days)\n\n"
            f"🍽️ Total Meals: {stats.total_meals}\n\n"
            f"⚡ Calories:\n"
            f"  • Total: {stats.total_calories:.0f} kcal\n"
            f"  • Daily Avg: {stats.avg_calories:.0f} kcal\n\n"
            f"💪 Protein:\n"
            f"  • Total: {stats.total_protein:.1f}g\n"
            f"  • Daily Avg: {stats.avg_protein:.1f}g\n\n"
            f"🍬 Sugar: {stats.avg_sugar:.1f}g/day\n"
            f"🍞 Carbs: {stats.avg_carbs:.1f}g/day\n"
            f"🥑 Fat: {stats.avg_fat:.1f}g/day\n"
            f"🌾 Fiber: {stats.avg_fiber:.1f}g/day\n\n"
            f"💚 Avg Health Score: {stats.avg_health_score:.0f}/100"
        )


class GetWeeklySummaryUseCase:
    """
    Use case for getting weekly nutrition summary.

    Used by:
    - /summary telegram command
    - GET /statistics API endpoint
    - Email reports (future)
    """

    def __init__(self, repository: FoodAnalysisRepository):
        self.repository = repository

    async def execute(self, input: GetWeeklySummaryInput) -> GetWeeklySummaryOutput:
        """
        Get aggregated nutrition statistics.

        Args:
            input: GetWeeklySummaryInput with time range

        Returns:
            GetWeeklySummaryOutput with statistics
        """
        logfire.info(
            "Getting weekly summary",
            days=input.days,
            user_id=input.user_id
        )

        statistics = await self.repository.get_statistics(days=input.days)

        logfire.info(
            "Weekly summary retrieved",
            total_meals=statistics.total_meals,
            avg_calories=statistics.avg_calories
        )

        return GetWeeklySummaryOutput(statistics=statistics)
```

**Update statistics endpoint:**
```python
@app.get("/statistics", tags=["Statistics"])
async def get_statistics(
    days: int = 7,
    use_case: GetWeeklySummaryUseCase = Depends(get_weekly_summary_use_case)
):
    """Get nutrition statistics for the last N days."""
    input = GetWeeklySummaryInput(days=days)
    output = await use_case.execute(input)
    return output.statistics.to_dict()
```

**Acceptance Criteria:**
- [ ] Use case implements weekly summary logic
- [ ] Has telegram message formatting method
- [ ] API endpoint uses the use case
- [ ] Ready for telegram /summary command
- [ ] Handles empty result sets gracefully

---

#### Task 3.3: Create GetAnalysisHistoryUseCase
**File:** Create `backend/use_cases/get_analysis_history.py`
**Priority:** MEDIUM
**Estimated Time:** 30 minutes

**Implementation:**
```python
# backend/use_cases/get_analysis_history.py
from dataclasses import dataclass
from typing import List

import logfire

from backend.domain.entities import FoodAnalysis
from backend.repositories.food_analysis_repository import FoodAnalysisRepository


@dataclass
class GetAnalysisHistoryInput:
    """Input for GetAnalysisHistoryUseCase"""
    limit: int = 10
    offset: int = 0
    user_id: str | None = None


@dataclass
class GetAnalysisHistoryOutput:
    """Output from GetAnalysisHistoryUseCase"""
    analyses: List[FoodAnalysis]
    total: int


class GetAnalysisHistoryUseCase:
    """
    Use case for retrieving analysis history with pagination.

    Used by:
    - GET /history API endpoint
    - Dashboard UI (future)
    """

    def __init__(self, repository: FoodAnalysisRepository):
        self.repository = repository

    async def execute(self, input: GetAnalysisHistoryInput) -> GetAnalysisHistoryOutput:
        """
        Get paginated analysis history.

        Args:
            input: GetAnalysisHistoryInput with pagination params

        Returns:
            GetAnalysisHistoryOutput with analyses and count
        """
        logfire.debug(
            "Getting analysis history",
            limit=input.limit,
            offset=input.offset,
            user_id=input.user_id
        )

        analyses = await self.repository.find_recent(
            limit=input.limit,
            offset=input.offset
        )

        logfire.info(f"Retrieved {len(analyses)} analyses")

        return GetAnalysisHistoryOutput(
            analyses=analyses,
            total=len(analyses)
        )
```

**Update history endpoint:**
```python
@app.get("/history", tags=["History"])
async def get_history(
    limit: int = 10,
    offset: int = 0,
    use_case: GetAnalysisHistoryUseCase = Depends(get_history_use_case)
):
    """Get recent analysis history."""
    input = GetAnalysisHistoryInput(limit=limit, offset=offset)
    output = await use_case.execute(input)

    return {
        "total": output.total,
        "data": [a.to_dict() for a in output.analyses]
    }
```

**Acceptance Criteria:**
- [ ] Use case implements history retrieval
- [ ] Supports pagination
- [ ] API endpoint uses the use case
- [ ] Returns consistent response format

---

### PHASE 4: Telegram Command Pattern

#### Task 4.1: Create TelegramBotService
**File:** Create `backend/services/telegram_bot_service.py`
**Priority:** MEDIUM
**Estimated Time:** 2 hours

**Implementation:**
```python
# backend/services/telegram_bot_service.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional

import httpx
import logfire

from backend.config import Settings


@dataclass
class BotContext:
    """Context passed to telegram commands"""
    settings: Settings
    http_client: httpx.AsyncClient


class TelegramCommand(ABC):
    """Abstract base class for telegram commands"""

    @abstractmethod
    async def execute(self, message: dict, context: BotContext) -> str:
        """
        Execute the command and return response text.

        Args:
            message: Telegram message dict
            context: Bot context with settings and HTTP client

        Returns:
            Response text to send to user
        """
        pass

    @abstractmethod
    def get_help_text(self) -> str:
        """Get help text for this command"""
        pass


class StartCommand(TelegramCommand):
    """Handler for /start command"""

    async def execute(self, message: dict, context: BotContext) -> str:
        return (
            "👋 Welcome to Food Analysis Bot!\n\n"
            "Send me a photo of your food and I'll analyze:\n"
            "• Nutritional content\n"
            "• Calories and macros\n"
            "• Health score\n\n"
            "Available commands:\n"
            "/summary - Get your weekly nutrition summary\n"
            "/help - Show this help message"
        )

    def get_help_text(self) -> str:
        return "/start - Start the bot and see welcome message"


class HelpCommand(TelegramCommand):
    """Handler for /help command"""

    def __init__(self, commands: Dict[str, TelegramCommand]):
        self.commands = commands

    async def execute(self, message: dict, context: BotContext) -> str:
        help_texts = [cmd.get_help_text() for cmd in self.commands.values()]
        return (
            "🤖 Food Analysis Bot Commands\n\n"
            + "\n".join(help_texts) +
            "\n\n📸 You can also just send a photo of your food!"
        )

    def get_help_text(self) -> str:
        return "/help - Show available commands"


class TelegramBotService:
    """Service for handling Telegram bot interactions"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.commands: Dict[str, TelegramCommand] = {}

        # Register built-in commands
        self.register_command("start", StartCommand())

        logfire.info("Telegram bot service initialized")

    def register_command(self, name: str, command: TelegramCommand) -> None:
        """Register a command handler"""
        self.commands[name] = command
        logfire.debug(f"Registered telegram command: /{name}")

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None
    ) -> bool:
        """
        Send a text message to a chat.

        Args:
            chat_id: Telegram chat ID
            text: Message text
            parse_mode: Optional parse mode (Markdown, HTML)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.settings.telegram_bot_token:
            logfire.warning("Cannot send message: bot token not configured")
            return False

        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logfire.debug("Message sent", chat_id=chat_id)
                return True
        except Exception as exc:
            logfire.error(f"Failed to send message: {exc}", chat_id=chat_id)
            return False

    async def handle_update(self, update: dict) -> Optional[str]:
        """
        Process a telegram update.

        Args:
            update: Telegram update dict

        Returns:
            Response text if handled, None otherwise
        """
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        chat_id = message.get("chat", {}).get("id")
        if not chat_id:
            return None

        text = message.get("text", "").strip()

        # Handle commands
        if text.startswith("/"):
            command_parts = text.split(maxsplit=1)
            command_name = command_parts[0][1:].split("@")[0]  # Remove / and @botname

            command = self.commands.get(command_name)
            if command:
                try:
                    async with httpx.AsyncClient() as client:
                        context = BotContext(
                            settings=self.settings,
                            http_client=client
                        )
                        response = await command.execute(message, context)
                        await self.send_message(chat_id, response)
                        return response
                except Exception as exc:
                    logfire.error(f"Command execution failed: {exc}", command=command_name)
                    error_msg = "Sorry, something went wrong processing your command."
                    await self.send_message(chat_id, error_msg)
                    return error_msg
            else:
                response = f"Unknown command: /{command_name}\n\nUse /help to see available commands."
                await self.send_message(chat_id, response)
                return response

        # Not a command - will be handled by other handlers (photo, etc.)
        return None

    def register_help_command(self) -> None:
        """Register the help command (call after all commands are registered)"""
        self.register_command("help", HelpCommand(self.commands))
```

**Acceptance Criteria:**
- [ ] TelegramBotService class created
- [ ] Command pattern implemented
- [ ] StartCommand and HelpCommand work
- [ ] Easy to register new commands
- [ ] Message sending abstracted

---

#### Task 4.2: Create SummaryCommand
**File:** Update `backend/services/telegram_bot_service.py`
**Priority:** HIGH
**Estimated Time:** 45 minutes

**Implementation:**
```python
# Add to backend/services/telegram_bot_service.py

class SummaryCommand(TelegramCommand):
    """Handler for /summary command"""

    def __init__(self, use_case):
        """
        Args:
            use_case: GetWeeklySummaryUseCase instance
        """
        self.use_case = use_case

    async def execute(self, message: dict, context: BotContext) -> str:
        from backend.use_cases.get_weekly_summary import GetWeeklySummaryInput

        try:
            # Get weekly summary
            input = GetWeeklySummaryInput(days=7)
            output = await self.use_case.execute(input)

            # Format as telegram message
            return output.format_telegram_message()

        except Exception as exc:
            logfire.error(f"Failed to get summary: {exc}")
            return (
                "Sorry, I couldn't retrieve your weekly summary. "
                "Please try again later."
            )

    def get_help_text(self) -> str:
        return "/summary - Get your weekly nutrition summary (last 7 days)"
```

**Update main.py lifespan:**
```python
# In lifespan function, after creating use cases
summary_use_case = GetWeeklySummaryUseCase(
    repository=app.state.food_repository
)

telegram_bot = TelegramBotService(settings)
telegram_bot.register_command("summary", SummaryCommand(summary_use_case))
telegram_bot.register_help_command()  # Must be last

app.state.telegram_bot = telegram_bot
```

**Acceptance Criteria:**
- [ ] SummaryCommand implemented
- [ ] Uses GetWeeklySummaryUseCase
- [ ] Formats output nicely for Telegram
- [ ] Handles errors gracefully
- [ ] /summary command works in Telegram

**Testing:**
```
# In Telegram, send:
/summary

# Should receive formatted weekly statistics
```

---

#### Task 4.3: Create PhotoAnalysisCommand
**File:** Update `backend/services/telegram_bot_service.py`
**Priority:** MEDIUM
**Estimated Time:** 1 hour

**Implementation:**
```python
# Add to backend/services/telegram_bot_service.py

class PhotoAnalysisCommand(TelegramCommand):
    """Handler for photo messages (not a slash command)"""

    def __init__(self, use_case, telegram_bot):
        """
        Args:
            use_case: AnalyzeFoodImageUseCase instance
            telegram_bot: TelegramBotService for sending messages
        """
        self.use_case = use_case
        self.telegram_bot = telegram_bot

    async def execute(self, message: dict, context: BotContext) -> str:
        from backend.use_cases.analyze_food_image import AnalyzeFoodImageInput

        chat_id = message["chat"]["id"]
        photos = message.get("photo", [])

        if not photos:
            return "Please send a photo of your food."

        try:
            # Get largest photo
            file_id = photos[-1]["file_id"]
            caption = message.get("caption", "")

            # Send "analyzing" message
            await self.telegram_bot.send_message(
                chat_id,
                "🔍 Analyzing your food image..."
            )

            # Download file from Telegram
            image_data, filename = await self._download_telegram_file(
                file_id,
                context
            )

            # Analyze image
            input = AnalyzeFoodImageInput(
                image_data=image_data,
                filename=caption[:64] if caption else filename
            )
            output = await self.use_case.execute(input)

            # Format response
            analysis = output.analysis
            n = analysis.nutrition

            return (
                f"✅ Analysis Complete!\n\n"
                f"🍽️ Food: {n.food_name}\n\n"
                f"📊 Nutrition Facts:\n"
                f"⚡ Calories: {n.calories:.0f} kcal\n"
                f"💪 Protein: {n.protein:.1f}g\n"
                f"🍬 Sugar: {n.sugar:.1f}g\n"
                f"🥑 Fat: {n.fat:.1f}g\n"
                f"🌾 Fiber: {n.fiber:.1f}g\n"
                f"🍞 Carbs: {n.carbs:.1f}g\n\n"
                f"💚 Health Score: {n.health_score or 0}/100\n\n"
                f"Use /summary to see your weekly stats!"
            )

        except Exception as exc:
            logfire.error(f"Photo analysis failed: {exc}")
            return (
                "❌ Sorry, I couldn't analyze this image. "
                "Please make sure it's a clear photo of food and try again."
            )

    async def _download_telegram_file(
        self,
        file_id: str,
        context: BotContext
    ) -> tuple[bytes, str]:
        """Download file from Telegram"""
        base_url = f"https://api.telegram.org/bot{context.settings.telegram_bot_token}"

        # Get file path
        resp = await context.http_client.get(
            f"{base_url}/getFile",
            params={"file_id": file_id}
        )
        resp.raise_for_status()

        file_info = resp.json()["result"]
        file_path = file_info["file_path"]

        # Download file
        download_url = f"https://api.telegram.org/file/bot{context.settings.telegram_bot_token}/{file_path}"
        resp = await context.http_client.get(download_url)
        resp.raise_for_status()

        filename = file_path.rsplit("/", 1)[-1]
        return resp.content, filename

    def get_help_text(self) -> str:
        return "📸 Send a photo - Analyze food and get nutrition info"


# Update TelegramBotService to handle photos
class TelegramBotService:
    # ... existing code ...

    async def handle_update(self, update: dict) -> Optional[str]:
        message = update.get("message") or update.get("edited_message")
        if not message:
            return None

        chat_id = message.get("chat", {}).get("id")
        if not chat_id:
            return None

        text = message.get("text", "").strip()

        # Handle text commands
        if text.startswith("/"):
            # ... existing command handling ...
            pass

        # Handle photos
        elif message.get("photo"):
            photo_command = self.commands.get("__photo__")
            if photo_command:
                try:
                    async with httpx.AsyncClient(timeout=60) as client:
                        context = BotContext(
                            settings=self.settings,
                            http_client=client
                        )
                        response = await photo_command.execute(message, context)
                        await self.send_message(chat_id, response)
                        return response
                except Exception as exc:
                    logfire.error(f"Photo handling failed: {exc}")
                    error_msg = "Sorry, I couldn't process that image."
                    await self.send_message(chat_id, error_msg)
                    return error_msg

        return None
```

**Update main.py:**
```python
# In lifespan, register photo handler
analyze_use_case = AnalyzeFoodImageUseCase(
    analyzer=app.state.gemini_analyzer,
    storage=app.state.storage_service,
    repository=app.state.food_repository,
    max_image_size_mb=settings.max_image_size_mb
)

telegram_bot = TelegramBotService(settings)
telegram_bot.register_command("summary", SummaryCommand(summary_use_case))
telegram_bot.register_command("__photo__", PhotoAnalysisCommand(analyze_use_case, telegram_bot))
telegram_bot.register_help_command()
```

**Acceptance Criteria:**
- [ ] PhotoAnalysisCommand handles photo messages
- [ ] Downloads from Telegram properly
- [ ] Uses AnalyzeFoodImageUseCase
- [ ] Formats response nicely
- [ ] Error handling works

---

### PHASE 5: Structure Cleanup

#### Task 5.1: Split main.py into Routers
**Files:** Create router files
**Priority:** MEDIUM
**Estimated Time:** 2 hours

**Create router structure:**

```python
# backend/routes/analysis.py
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
import logfire

from backend.api.responses import FoodAnalysisResponse
from backend.api.requests import FoodAnalysisRequest
from backend.use_cases.analyze_food_image import (
    AnalyzeFoodImageUseCase,
    AnalyzeFoodImageInput
)
from backend.services.image_utils import decode_base64_image

router = APIRouter(prefix="/analyze", tags=["Analysis"])


@router.post("", response_model=FoodAnalysisResponse)
async def analyze_food_image(
    file: UploadFile = File(...),
    use_case: AnalyzeFoodImageUseCase = Depends(...),
):
    """Analyze a food image from file upload."""
    try:
        image_data = await file.read()
        input = AnalyzeFoodImageInput(
            image_data=image_data,
            filename=file.filename or "upload.jpg"
        )

        output = await use_case.execute(input)
        return FoodAnalysisResponse.from_domain(output.analysis)

    except ValueError as exc:
        logfire.warning(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logfire.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")


@router.post("/base64", response_model=FoodAnalysisResponse)
async def analyze_food_image_base64(
    request: FoodAnalysisRequest,
    use_case: AnalyzeFoodImageUseCase = Depends(...),
):
    """Analyze a food image from base64 data."""
    try:
        image_data = decode_base64_image(request.image_data)
        input = AnalyzeFoodImageInput(
            image_data=image_data,
            filename=request.filename or "image.jpg"
        )

        output = await use_case.execute(input)
        return FoodAnalysisResponse.from_domain(output.analysis)

    except ValueError as exc:
        logfire.warning(f"Validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logfire.error(f"Analysis error: {exc}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")
```

```python
# backend/routes/history.py
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID

from backend.use_cases.get_analysis_history import (
    GetAnalysisHistoryUseCase,
    GetAnalysisHistoryInput
)
from backend.use_cases.get_weekly_summary import (
    GetWeeklySummaryUseCase,
    GetWeeklySummaryInput
)
from backend.repositories.food_analysis_repository import FoodAnalysisRepository

router = APIRouter(tags=["History"])


@router.get("/analysis/{analysis_id}")
async def get_analysis(
    analysis_id: UUID,
    repository: FoodAnalysisRepository = Depends(...)
):
    """Get a specific analysis by ID."""
    analysis = await repository.find_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis.to_dict()


@router.get("/history")
async def get_history(
    limit: int = 10,
    offset: int = 0,
    use_case: GetAnalysisHistoryUseCase = Depends(...)
):
    """Get recent analysis history."""
    input = GetAnalysisHistoryInput(limit=limit, offset=offset)
    output = await use_case.execute(input)

    return {
        "total": output.total,
        "data": [a.to_dict() for a in output.analyses]
    }


@router.get("/statistics")
async def get_statistics(
    days: int = 7,
    use_case: GetWeeklySummaryUseCase = Depends(...)
):
    """Get nutrition statistics."""
    input = GetWeeklySummaryInput(days=days)
    output = await use_case.execute(input)
    return output.statistics.to_dict()


@router.delete("/analysis/{analysis_id}")
async def delete_analysis(
    analysis_id: UUID,
    repository: FoodAnalysisRepository = Depends(...),
    storage: StorageService = Depends(...)
):
    """Delete an analysis and its image."""
    analysis = await repository.find_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    # Delete from database
    await repository.delete(analysis_id)

    # Delete from storage (best effort)
    filename = analysis.image_url.split("/")[-1]
    await storage.delete_image(filename)

    return {"message": "Analysis deleted successfully"}
```

```python
# backend/routes/telegram.py
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.services.telegram_bot_service import TelegramBotService

router = APIRouter(prefix="/telegram", include_in_schema=False)


@router.post("/webhook")
async def telegram_webhook(
    update: dict,
    bot: TelegramBotService = Depends(...)
):
    """Telegram webhook handler."""
    try:
        response = await bot.handle_update(update)
        return JSONResponse(
            status_code=200,
            content={"ok": True, "handled": response is not None}
        )
    except Exception as exc:
        logfire.error(f"Telegram webhook error: {exc}")
        return JSONResponse(
            status_code=200,  # Always return 200 to Telegram
            content={"ok": False, "error": str(exc)}
        )
```

```python
# backend/routes/health.py
from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "food-analysis-api",
        "version": "1.0.0"
    }
```

**Update main.py to be minimal:**
```python
# main.py (new minimal version)
import logfire
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from backend.config import Settings
from backend.routes import analysis, history, telegram, health
from backend.api.dependencies import setup_dependencies

settings = Settings()

if settings.logfire_write_token:
    logfire.configure(token=settings.logfire_write_token)
else:
    logfire.configure()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan."""
    logfire.info("Application starting up...")

    # Setup dependencies (creates services, use cases, etc.)
    await setup_dependencies(app, settings)

    yield

    # Cleanup
    logfire.info("Application shutting down...")


app = FastAPI(
    title="Food Image Analysis API",
    description="API for analyzing food images using Gemini AI",
    version="1.0.0",
    lifespan=lifespan,
)

logfire.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(analysis.router)
app.include_router(history.router)
app.include_router(telegram.router)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

**Acceptance Criteria:**
- [ ] main.py under 100 lines
- [ ] Routers created and organized
- [ ] All endpoints still work
- [ ] Dependency injection centralized
- [ ] Clean separation of concerns

---

### PHASE 6: Testing & Documentation

#### ✅ Task 6.1: Unit Tests for Analysis Service
**File:** `tests/unit/test_analysis.service.py` ✅ **COMPLETED**
**Status:** DONE
**Lines of Code:** 66

**Implemented Tests:**
- ✅ `test_analyze_and_store_calls_all_services()` - Verifies complete workflow
- Uses proper mocking for analyzer, storage, database
- Tests service integration with valid PNG image
- Verifies all services called in correct order

**Coverage:**
- AnalysisService workflow
- Service integration patterns
- Result structure validation

---

#### ✅ Task 6.2: Integration Tests for API Endpoints
**File:** `tests/integration/test_api_endpoints.py` ✅ **COMPLETED**
**Status:** DONE
**Lines of Code:** 484 (Comprehensive!)

**Test Coverage by Priority:**

**Priority 1-2: Core Endpoints (2 tests)**
- ✅ Health check endpoint
- ✅ Statistics endpoint returns data

**Priority 3-4: History & Retrieval (4 tests)**
- ✅ History endpoint returns data
- ✅ History respects limit parameter
- ✅ Get analysis by ID (404 case)
- ✅ Delete analysis (404 case)

**Priority 5-7: Error Handling (9 tests)**
- ✅ Analyze endpoint: no file, empty file, invalid file type
- ✅ Base64 endpoint: missing data, invalid base64, empty data

**Priority 8-9: Edge Cases (11 tests)**
- ✅ History: zero/negative/large limits, offset pagination
- ✅ Statistics: zero/negative/large days, default days
- ✅ Different day ranges (7 vs 30 days)

**Priority 10: Schema Validation (2 tests)**
- ✅ Statistics response type checking
- ✅ History response structure validation

**Priority 11-12: HTTP Standards (5 tests)**
- ✅ Content type validation
- ✅ Method restrictions (GET/POST)
- ✅ CORS headers
- ✅ JSON content type

**Priority 13: Error Formats (2 tests)**
- ✅ 404 error detail format
- ✅ 422 validation error format

**Bonus (2 tests)**
- ✅ Root redirects to /docs
- ✅ Docs endpoint accessible

**Total: 37 comprehensive integration tests!**

**Acceptance Criteria:**
- ✅ Integration tests for all endpoints
- ✅ Test with real HTTP requests (TestClient)
- ✅ Validate response schemas
- ✅ Edge case coverage
- ✅ Error handling validation

---

#### ✅ Task 6.3: Integration Tests for Database Service
**File:** `tests/integration/test_intergration_database_service.py` ✅ **COMPLETED**
**Status:** DONE
**Lines of Code:** 66

**Implemented Tests:**
- ✅ `test_save_and_retrieve_real_analysis()` - Full CRUD with real database
- ✅ `test_get_statistics_real_data()` - Statistics with real data
- Uses real Supabase test table (not mocked!)
- Includes cleanup after tests

**Coverage:**
- Real database operations
- Save, retrieve, delete workflows
- Statistics calculation with actual data

---

#### ✅ Task 6.4: Unit Tests for Storage Service
**File:** `tests/integration/test_storage_service.py` ✅ **COMPLETED**
**Status:** DONE
**Lines of Code:** 60

**Implemented Tests:**
- ✅ `test_upload_image_success()` - Image upload with mocked client
- ✅ `test_delete_image_success()` - Image deletion
- Uses proper mocking of Supabase client
- Verifies storage operations

**Coverage:**
- Storage service upload workflow
- Storage service delete workflow
- Mock-based unit testing patterns

---

#### Task 6.5: Update Documentation
**Files:** README.md, new ARCHITECTURE.md
**Priority:** LOW
**Estimated Time:** 1.5 hours
**Status:** PENDING

**Create ARCHITECTURE.md:**
```markdown
# Architecture Documentation

## Overview
This application follows Clean Architecture principles with clear layer separation.

## Layers

### 1. Domain Layer (`backend/domain/`)
- Pure business logic and entities
- No framework dependencies
- Independent of external services

### 2. Use Case Layer (`backend/use_cases/`)
- Application business rules
- Orchestrates domain entities
- Calls repositories and services

### 3. Repository Layer (`backend/repositories/`)
- Data access abstraction
- Hides persistence details
- Easy to swap implementations

### 4. Service Layer (`backend/services/`)
- External integrations (Gemini, Storage, Telegram)
- Infrastructure concerns
- Framework-specific code

### 5. API Layer (`backend/routes/`)
- HTTP request/response handling
- Input validation
- Calls use cases

## Design Patterns

### Repository Pattern
Abstracts data access behind interfaces.

### Use Case Pattern
Encapsulates business logic in single-responsibility classes.

### Command Pattern
Handles different Telegram commands extensibly.

## Data Flow

```
HTTP Request → Router → Use Case → Repository → Database
                          ↓
                       Services (Gemini, Storage)
```

## Testing Strategy
- Unit tests: Use cases, domain entities
- Integration tests: Repositories, API endpoints
- E2E tests: Full workflows
```

**Update README.md:**
- Add link to ARCHITECTURE.md
- Update project structure section
- Add development setup instructions
- Document how to add new features

**Acceptance Criteria:**
- [ ] ARCHITECTURE.md created
- [ ] README.md updated
- [ ] Clear onboarding instructions
- [ ] Examples of extending the system

---

## Success Metrics

### Code Quality Metrics
- [ ] main.py under 100 lines
- [ ] Average file size under 200 lines
- [ ] Test coverage above 80%
- [ ] No code duplication (DRY principle)
- [ ] All endpoints functional

### Architecture Metrics
- [ ] Clear layer boundaries
- [ ] Repository pattern implemented
- [ ] Use cases for all business logic
- [ ] Command pattern for Telegram
- [ ] No circular dependencies

### Feature Completeness
- [ ] Image upload → analysis works
- [ ] `/summary` command works
- [ ] `/history` endpoint works
- [ ] `/statistics` endpoint works
- [ ] Telegram photo analysis works
- [ ] Telegram `/start`, `/help`, `/summary` work

### Developer Experience
- [ ] Easy to add new features
- [ ] Clear where to put new code
- [ ] Comprehensive documentation
- [ ] Fast test execution
- [ ] Good error messages

---

## Timeline Summary

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1: Critical Fixes | 2-3 days | Missing methods implemented, duplicate code removed |
| Phase 2: Repository Pattern | 3-4 days | Data access abstracted, testable |
| Phase 3: Use Case Layer | 4-5 days | Business logic reusable |
| Phase 4: Telegram Commands | 2-3 days | `/summary` working, extensible commands |
| Phase 5: Structure Cleanup | 3-4 days | Modular codebase, clear boundaries |
| Phase 6: Testing & Docs | 3-4 days | 80%+ coverage, comprehensive docs |
| **Total** | **17-23 days** | **Production-ready architecture** |

---

## Next Steps

1. Review this plan with the team
2. Prioritize phases based on business needs
3. Start with Phase 1 (critical fixes)
4. Set up CI/CD pipeline for automated testing
5. Schedule code reviews after each phase

---

## Questions or Concerns?

If you have questions about any of these tasks or need clarification on the architecture decisions, please reach out to the Tech Lead.

---

**Document Version:** 1.0
**Last Updated:** 2025-12-29
**Author:** Tech Lead Review
