"""
Test the Crawler API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["name"] == "Job Crawler API"


def test_health():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_get_sources():
    """Test get sources endpoint."""
    response = client.get("/api/v1/sources")
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data
    assert len(data["sources"]) >= 3
    
    sources = [s["id"] for s in data["sources"]]
    assert "itviec" in sources
    assert "topdev" in sources
    assert "linkedin" in sources


def test_create_job():
    """Test creating a crawl job."""
    response = client.post(
        "/api/v1/crawl",
        json={
            "source": "linkedin",
            "keywords": ["test"],
            "pages": 1,
            "headless": True
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] in ["pending", "running"]
    assert data["source"] == "linkedin"


def test_create_job_invalid_source():
    """Test creating job with invalid source."""
    response = client.post(
        "/api/v1/crawl",
        json={
            "source": "invalid",
            "keywords": ["test"],
            "pages": 1
        }
    )
    assert response.status_code == 400


def test_get_job():
    """Test getting job status."""
    # First create a job
    create_response = client.post(
        "/api/v1/crawl",
        json={
            "source": "itviec",
            "keywords": ["python"],
            "pages": 1,
            "headless": True
        }
    )
    job_id = create_response.json()["job_id"]
    
    # Then get the job
    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert "status" in data


def test_get_nonexistent_job():
    """Test getting a non-existent job."""
    response = client.get("/api/v1/jobs/nonexistent-job-id")
    assert response.status_code == 404


def test_list_jobs():
    """Test listing jobs."""
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data


def test_list_jobs_with_filters():
    """Test listing jobs with filters."""
    # Create a job first
    client.post(
        "/api/v1/crawl",
        json={
            "source": "topdev",
            "keywords": ["javascript"],
            "pages": 1
        }
    )
    
    # List with source filter
    response = client.get("/api/v1/jobs?source=topdev")
    assert response.status_code == 200
    data = response.json()
    for job in data["jobs"]:
        assert job["source"] == "topdev"


def test_cancel_job():
    """Test cancelling a job."""
    # Create a job
    create_response = client.post(
        "/api/v1/crawl",
        json={
            "source": "linkedin",
            "keywords": ["test"],
            "pages": 1
        }
    )
    job_id = create_response.json()["job_id"]
    
    # Cancel it
    response = client.delete(f"/api/v1/jobs/{job_id}")
    # Note: This might return 200 or 404 depending on job state
    assert response.status_code in [200, 404]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
