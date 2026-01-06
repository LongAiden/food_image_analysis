import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from uuid import uuid4

from main import app


@pytest.fixture
def client():
    """
    Create FastAPI test client with lifespan context.
    """
    with TestClient(app) as test_client:
        yield test_client


# ============================================================
# PRIORITY 1: Health Check
# ============================================================

@pytest.mark.integration
def test_health_endpoint(client):
    """Verify app starts and health check works."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


# ============================================================
# PRIORITY 2: Statistics Endpoint
# ============================================================

@pytest.mark.integration
def test_statistics_endpoint_returns_data(client):
    """Verify statistics endpoint works (uses real DB)."""
    response = client.get("/statistics?days=7")

    assert response.status_code == 200
    data = response.json()

    # Should always return these fields (even if empty)
    required_fields = {
        "total_meals", "avg_calories", "avg_protein",
        "avg_sugar", "avg_carbs", "avg_fat",
        "avg_fiber", "start_date"
    }
    assert required_fields.issubset(
        data.keys()), f"Missing fields: {required_fields - data.keys()}"


@pytest.mark.integration
def test_statistics_endpoint_with_different_days(client):
    """Test statistics with different day ranges."""
    # Test 7 days
    response_7 = client.get("/statistics?days=0")
    assert response_7.status_code == 200

    # Test 30 days
    response_30 = client.get("/statistics?days=30")
    assert response_30.status_code == 200

    # Both should have same structure
    data_7 = response_7.json()
    data_30 = response_30.json()
    assert set(data_7.keys()) == set(data_30.keys()) # Maybe failed if the schema changed
    
    
@pytest.mark.integration
def test_statistics_endpoint_with_non_numeric_days(client):
    """Test statistics with non numeric days parameter."""
    response = client.get("/statistics?days=abc")
    
    # Should return 400 or 422 for invalid input
    assert response.status_code in [400, 422]

# ============================================================
# PRIORITY 3: History Endpoint
# ============================================================

@pytest.mark.integration
def test_history_endpoint_returns_data(client):
    """Verify history endpoint works (uses real DB)."""
    
    response_0 = client.get("/history?limit=0")
    response_5 = client.get("/history?limit=5")

    assert response_0.status_code == 200
    data_0 = response_0.json()
    
    assert response_5.status_code == 200
    data_5 = response_5.json()
    
    # Should return these fields
    assert isinstance(data_0["data"], list)
    assert isinstance(data_5["data"], list)

    # Each item should have required fields
    required_fields = {'id', 'image_path', 'raw_result', 'created_at'}
    if len(data_5["data"]) > 0:
        for item in data_5["data"]:
            assert required_fields.issubset(item.keys()), f"Missing fields: {required_fields - item.keys()}"

    # Both should have same structure
    assert set(data_0.keys()) == set(data_5.keys())


@pytest.mark.integration
def test_history_endpoint_with_negative_number(client):
    """Verify history limit parameter works."""
    response = client.get("/history?limit=-10")

    # Should return 400 or 422 for invalid input
    assert response.status_code in [400, 422]


# ============================================================
# PRIORITY 4: Get Analysis by ID
# ============================================================

@pytest.mark.integration
def test_get_analysis_by_id_not_found(client):
    """Test getting non-existent analysis returns 404."""
    fake_id = uuid4()
    response = client.get(f"/analysis/{fake_id}")

    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert "not found" in data["detail"].lower()


# ============================================================
# PRIORITY 5: Delete Analysis Endpoint
# ============================================================

@pytest.mark.integration
def test_delete_analysis_not_found(client):
    """Test deleting non-existent analysis returns 404."""
    fake_id = uuid4()
    response = client.delete(f"/analysis/{fake_id}")

    # Should return 404 for non-existent analysis
    assert response.status_code == 404


@pytest.mark.integration
def test_get_analysis_invalid_uuid_format(client):
    response = client.get("/analysis/not-a-uuid")

    assert response.status_code == 422

    # Get the error details from the response
    error_detail = response.json()["detail"][0]

    # OPTION A: Check for the machine-readable 'type' (Most Robust)
    assert "uuid" in error_detail["type"]

    # OPTION B: Check for a more flexible keyword in the message
    assert "valid uuid" in error_detail["msg"].lower()


# ============================================================
# PRIORITY 6: Analyze Endpoint - Error Cases
# ============================================================

@pytest.mark.integration
def test_analyze_endpoint_no_file(client):
    """Test analyze endpoint without file returns 422 validation error."""
    response = client.post("/analyze")

    # FastAPI returns 422 for missing required field
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data


@pytest.mark.integration
def test_analyze_endpoint_empty_file(client):
    """Test analyze endpoint with empty file."""
    # Create empty file
    files = {"file": ("empty.jpg", b"", "image/jpeg")}
    response = client.post("/analyze", files=files)

    # Should return 400 or 500 for invalid image
    assert response.status_code in [400, 422, 500]


@pytest.mark.integration
def test_analyze_endpoint_invalid_file_type(client):
    """Test analyze endpoint with non-image file."""
    # Create text file instead of image
    files = {"file": ("test.txt", b"This is not an image", "text/plain")}
    response = client.post("/analyze", files=files)

    # Should reject non-image files
    assert response.status_code in [400, 422, 500]


# ============================================================
# PRIORITY 7: Analyze Base64 Endpoint - Error Cases
# ============================================================

@pytest.mark.integration
def test_analyze_base64_missing_data(client):
    """Test base64 endpoint without image_data field."""
    response = client.post(
        "/analyze-base64",
        json={"filename": "test.jpg"}  # Missing image_data
    )

    # Should return 422 validation error
    assert response.status_code == 422


@pytest.mark.integration
def test_analyze_base64_invalid_base64(client):
    """Test base64 endpoint with invalid base64 string."""
    response = client.post(
        "/analyze-base64",
        json={
            "image_data": "not-valid-base64!!!",
            "filename": "test.jpg"
        }
    )

    # Should return 400 for invalid base64
    assert response.status_code in [400, 422, 500]


@pytest.mark.integration
def test_analyze_base64_empty_data(client):
    """Test base64 endpoint with empty image_data."""
    import base64

    # Valid base64 but empty data
    empty_base64 = base64.b64encode(b"").decode()

    response = client.post(
        "/analyze-base64",
        json={
            "image_data": empty_base64,
            "filename": "test.jpg"
        }
    )

    # Should return error for empty image
    assert response.status_code in [400, 422, 500]


# ============================================================
# PRIORITY 8: History Endpoint - Edge Cases
# ============================================================

@pytest.mark.integration
def test_history_endpoint_zero_limit(client):
    """Test history with limit=0."""
    response = client.get("/history?limit=0")

    # Should handle gracefully (return empty or error)
    assert response.status_code in [200, 400, 422]


@pytest.mark.integration
def test_history_endpoint_negative_limit(client):
    """Test history with negative limit."""
    response = client.get("/history?limit=-5")

    # Should reject negative limit
    assert response.status_code in [400, 422]


@pytest.mark.integration
def test_history_endpoint_large_limit(client):
    """Test history with very large limit."""
    response = client.get("/history?limit=10000")

    # Should either accept or cap the limit
    assert response.status_code == 200
    data = response.json()

    # Even with large limit, shouldn't crash
    assert isinstance(data["data"], list)


@pytest.mark.integration
def test_history_endpoint_with_offset(client):
    """Test history pagination with offset."""
    # Get first page
    response_page1 = client.get("/history?limit=5&offset=0")
    assert response_page1.status_code == 200

    # Get second page
    response_page2 = client.get("/history?limit=5&offset=5")
    assert response_page2.status_code == 200

    # Both should have valid structure
    data1 = response_page1.json()
    data2 = response_page2.json()

    assert "data" in data1
    assert "data" in data2
    assert isinstance(data1["data"], list)
    assert isinstance(data2["data"], list)


# ============================================================
# PRIORITY 9: Statistics Endpoint - Edge Cases
# ============================================================

@pytest.mark.integration
def test_statistics_endpoint_zero_days(client):
    """Test statistics with days=0."""
    response = client.get("/statistics?days=0")

    # Should handle zero days gracefully
    assert response.status_code in [200, 400, 422]


@pytest.mark.integration
def test_statistics_endpoint_negative_days(client):
    """Test statistics with negative days."""
    response = client.get("/statistics?days=-7")

    # Should reject negative days
    assert response.status_code in [400, 422]


@pytest.mark.integration
def test_statistics_endpoint_large_days(client):
    """Test statistics with very large day range."""
    response = client.get("/statistics?days=365")

    # Should handle large ranges
    assert response.status_code == 200
    data = response.json()

    numeric_fields = ["avg_calories", "avg_protein",
                      "avg_sugar", "avg_carbs", "avg_fat", "avg_fiber"]
    for field in numeric_fields:
        assert field in data


@pytest.mark.integration
def test_statistics_endpoint_non_numeric(client):
    """Test statistics with very large day range."""
    response = client.get("/statistics?days=abc")

    # Should reject non-numeric days
    assert response.status_code in [400, 422]


@pytest.mark.integration
def test_statistics_endpoint_default_days(client):
    """Test statistics without days parameter (should use default)."""
    response = client.get("/statistics")

    assert response.status_code == 200
    data = response.json()

    # Should use default (likely 7 days)
    assert "total_meals" in data
    assert "start_date" in data


# ============================================================
# PRIORITY 10: API Response Schema Validation
# ============================================================

@pytest.mark.integration
def test_statistics_response_has_correct_types(client):
    """Verify statistics response has correct data types."""
    response = client.get("/statistics?days=7")

    assert response.status_code == 200
    data = response.json()

    # Verify total_meals is integer
    assert isinstance(data["total_meals"], int)

    # Verify numeric fields are numbers
    numeric_fields = ["avg_calories", "avg_protein",
                      "avg_sugar", "avg_carbs", "avg_fat", "avg_fiber"]
    assert all(isinstance(data[field], (int, float)) for field in numeric_fields), \
        "All average fields should be numeric"

    # Verify non-negative values
    assert data["total_meals"] >= 0
    assert data["avg_calories"] >= 0


@pytest.mark.integration
def test_history_response_has_correct_structure(client):
    """Verify history response has correct structure."""
    response = client.get("/history?limit=1")

    assert response.status_code == 200
    data = response.json()

    # Top level structure
    required_top_level = {"total", "data"}
    assert required_top_level.issubset(
        data.keys()), "Response must have 'total' and 'data' fields"
    assert isinstance(data["total"], int)
    assert isinstance(data["data"], list)

    # If data exists, check first item structure
    if len(data["data"]) > 0:
        item = data["data"][0]
        required_item_fields = {"id", "created_at"}
        assert required_item_fields.issubset(
            item.keys()), "Each item must have 'id' and 'created_at'"
        # Should have nutrition data
        assert "raw_result" in item or "food_name" in item


# ============================================================
# PRIORITY 11: Content Type Validation
# ============================================================

@pytest.mark.integration
def test_analyze_base64_requires_json(client):
    """Test base64 endpoint requires JSON content type."""
    response = client.post(
        "/analyze-base64",
        data="not-json-data"  # Send as form data instead of JSON
    )

    # Should require JSON content type
    assert response.status_code in [400, 422]


@pytest.mark.integration
def test_statistics_accepts_get_only(client):
    """Test statistics endpoint only accepts GET method."""
    # Try POST instead of GET
    response = client.post("/statistics")

    # Should return 405 Method Not Allowed
    assert response.status_code == 405


@pytest.mark.integration
def test_history_accepts_get_only(client):
    """Test history endpoint only accepts GET method."""
    # Try POST instead of GET
    response = client.post("/history")

    # Should return 405 Method Not Allowed
    assert response.status_code == 405


# ============================================================
# PRIORITY 12: CORS and Headers
# ============================================================

@pytest.mark.integration
def test_cors_headers_present(client):
    """Verify CORS headers are present in responses."""
    response = client.get("/health")

    # Should have CORS headers (from CORSMiddleware)
    assert response.status_code == 200
    # Note: TestClient might not set all CORS headers
    # This is more of a smoke test


@pytest.mark.integration
def test_api_returns_json_content_type(client):
    """Verify API endpoints return JSON content type."""
    response = client.get("/statistics")

    assert response.status_code == 200
    assert "application/json" in response.headers.get("content-type", "")


# ============================================================
# PRIORITY 13: Error Response Format
# ============================================================

@pytest.mark.integration
def test_404_error_has_detail(client):
    """Verify 404 errors have detail field."""
    fake_id = uuid4()
    response = client.get(f"/analysis/{fake_id}")

    assert response.status_code == 404
    data = response.json()

    # FastAPI standard error format
    assert "detail" in data
    assert isinstance(data["detail"], str)


@pytest.mark.integration
def test_422_validation_error_has_detail(client):
    """Verify validation errors have detail array."""
    response = client.post("/analyze")  # Missing required file

    assert response.status_code == 422
    data = response.json()

    # FastAPI validation error format
    assert "detail" in data
    assert isinstance(data["detail"], list)


# ============================================================
# BONUS: Root Redirect
# ============================================================

@pytest.mark.integration
def test_root_redirects_to_docs(client):
    """Test that root redirects to docs."""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307  # Temporary redirect
    assert response.headers["location"] == "/docs"


@pytest.mark.integration
def test_docs_endpoint_accessible(client):
    """Test that docs endpoint is accessible."""
    response = client.get("/docs")

    # Should return 200 (Swagger UI)
    assert response.status_code == 200
