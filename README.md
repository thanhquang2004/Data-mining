# 🕷️ Job Crawler - Data Mining Project

A comprehensive web crawler application for collecting IT job postings from Vietnamese job platforms. This is the **data collection** component of a larger data mining pipeline.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Folder Structure](#folder-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Data Schema](#data-schema)
- [Extending the Project](#extending-the-project)
- [Building Other Processes](#building-other-processes)
- [Contributing](#contributing)

---

## 🎯 Overview

This project is designed as the **first stage** of a data mining workflow:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DATA MINING PIPELINE                                    │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────────┤
│   1. COLLECT    │   2. PROCESS    │   3. ANALYZE    │      4. VISUALIZE        │
│   (This Repo)   │   (Future)      │   (Future)      │      (Dashboard)         │
├─────────────────┼─────────────────┼─────────────────┼──────────────────────────┤
│ • Web Crawlers  │ • Data Cleaning │ • ML Models     │ • Charts & Graphs        │
│ • API Service   │ • Normalization │ • NLP/NER       │ • Reports                │
│ • Raw Data      │ • Deduplication │ • Clustering    │ • Insights               │
│ • MySQL Storage │ • Enrichment    │ • Trend Analysis│ • Interactive UI         │
└─────────────────┴─────────────────┴─────────────────┴──────────────────────────┘
```

### Supported Job Platforms

| Platform                         | Status         | Features                                         |
| -------------------------------- | -------------- | ------------------------------------------------ |
| [ITViec](https://itviec.com)     | ✅ Active      | Cookie auth, Cloudflare bypass, full job details |
| [TopDev](https://topdev.vn)      | 🔧 In Progress | Basic crawling                                   |
| [LinkedIn](https://linkedin.com) | 🔧 In Progress | Requires authentication                          |

---

## ✨ Features

- **Multi-source Crawling**: Support for multiple job platforms
- **Playwright Integration**: Browser automation for JavaScript-heavy sites
- **Cloudflare Bypass**: Cookie-based authentication for protected sites
- **Rate Limiting**: Configurable delays to avoid detection
- **RESTful API**: FastAPI-based API for triggering and managing crawlers
- **Background Jobs**: Async crawl jobs with status tracking
- **MySQL Storage**: Persistent storage with SQLAlchemy ORM
- **Docker Support**: Containerized deployment ready
- **Data Export**: Raw JSON export for downstream processing

---

## 📁 Folder Structure

```
Data-mining-project/
│
├── api/                          # FastAPI Application
│   ├── __init__.py
│   ├── main.py                   # App entry point, routes, middleware
│   ├── models.py                 # Pydantic models for API requests/responses
│   ├── crawler_service.py        # Business logic for crawler management
│   └── dashboard.py              # Dashboard API endpoints
│
├── config/                       # Configuration Management
│   ├── __init__.py
│   └── setting.py                # Pydantic Settings (env variables)
│
├── src/                          # Core Source Code
│   ├── __init__.py
│   │
│   ├── crawlers/                 # Web Crawlers
│   │   ├── __init__.py           # Crawler factory function
│   │   ├── base_crawler.py       # Abstract base class
│   │   ├── itviec_crawler.py     # ITViec implementation
│   │   ├── topdev_crawler.py     # TopDev implementation
│   │   └── linkedin_crawler.py   # LinkedIn implementation
│   │
│   ├── database/                 # Database Layer
│   │   ├── __init__.py           # Exports for easy imports
│   │   ├── connection.py         # SQLAlchemy engine & session
│   │   └── models/               # ORM Models
│   │       ├── __init__.py
│   │       └── job/
│   │           ├── __init__.py
│   │           ├── job.py        # Job model definition
│   │           └── crud_job.py   # CRUD operations
│   │
│   └── schemas/                  # Pydantic Schemas
│       ├── __init__.py
│       └── job.py                # Job validation schemas
│
├── data/                         # Data Storage
│   ├── raw/                      # Raw crawled data (JSON)
│   ├── processed/                # Cleaned/processed data
│   └── skill_dictionaries/       # Reference data for skill extraction
│
├── certs/                        # SSL Certificates (for secure DB connections)
│   └── README.md
│
├── tests/                        # Test Suite
│   └── test_api.py
│
├── docker-compose.yml            # Docker orchestration
├── Dockerfile                    # Container definition
├── requirements.txt              # Python dependencies
├── .env                          # Environment variables (not in git)
├── run_api.py                    # Development server runner
├── init_db.py                    # Database initialization script
├── clean_data.py                 # Data cleaning utilities
└── itviec-session-cookies.json   # Session cookies for authenticated crawling
```

---

## 🔧 Prerequisites

- **Python 3.11+**
- **MySQL 8.0+** (or use Docker)
- **Docker & Docker Compose** (optional, for containerized deployment)

---

## 🚀 Installation

### Option 1: Local Development

```bash
# Clone the repository
git clone <your-repo-url>
cd Data-mining-project

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python init_db.py

# Run the API server
python run_api.py
# or: uvicorn api.main:app --reload
```

### Option 2: Docker Deployment

```bash
# Start all services (API + MySQL)
docker-compose up -d

# Development mode with hot-reload
docker-compose --profile dev up api-dev mysql

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

---

## ⚙️ Configuration

Create a `.env` file in the project root:

```env
# Application
DEBUG=false
LOG_LEVEL=INFO

# Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=job_crawler
MYSQL_USER=crawler_user
MYSQL_PASSWORD=your_secure_password
MYSQL_ROOT_PASSWORD=root_password

# SSL (optional)
DB_SSL_ENABLED=false
DB_SSL_CA=/app/certs/ca.pem
```

---

## 📖 Usage

### Start a Crawl Job via API

```bash
# Start crawling ITViec
curl -X POST "http://localhost:8000/api/v1/crawl" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "itviec",
    "keywords": ["python", "backend"],
    "location": "ho-chi-minh",
    "pages": 5,
    "max_jobs": 100,
    "fetch_details": true,
    "store_to_db": true
  }'

# Check job status
curl "http://localhost:8000/api/v1/jobs/{job_id}"

# List all jobs from database
curl "http://localhost:8000/api/v1/dashboard/jobs"
```

### Using Crawlers Directly (Python)

```python
from src.crawlers import create_crawler

# Create crawler instance
crawler = create_crawler(
    source="itviec",
    cookies_path="itviec-session-cookies.json",
    headless=True
)

# Run crawl
for job in crawler.crawl(
    keywords=["python"],
    pages=3,
    max_jobs=50,
    fetch_details=True
):
    print(f"Found: {job['title']} at {job['company_name']}")
```

---

## 🔌 API Reference

| Endpoint                  | Method | Description                    |
| ------------------------- | ------ | ------------------------------ |
| `/`                       | GET    | API information                |
| `/health`                 | GET    | Health check                   |
| `/api/v1/sources`         | GET    | List available crawler sources |
| `/api/v1/crawl`           | POST   | Start a new crawl job          |
| `/api/v1/jobs/{job_id}`   | GET    | Get crawl job status           |
| `/api/v1/jobs`            | GET    | List all crawl jobs            |
| `/api/v1/dashboard/jobs`  | GET    | Get jobs from database         |
| `/api/v1/dashboard/stats` | GET    | Get crawl statistics           |

---

## 📊 Data Schema

### Job Data Structure

```json
{
  "title": "Senior Python Developer",
  "company_name": "TechCorp Vietnam",
  "location": "Ho Chi Minh",
  "source": "itviec",
  "source_url": "https://itviec.com/it-jobs/...",
  "description": "Full job description...",
  "requirements_text": "Job requirements...",
  "job_type": "Full-time",
  "level": "Senior",
  "salary_min": 2000,
  "salary_max": 4000,
  "salary_currency": "USD",
  "experience_years_min": 3,
  "experience_years_max": 5,
  "required_skills": ["Python", "FastAPI", "PostgreSQL"],
  "preferred_skills": ["Docker", "Kubernetes"],
  "benefits": ["Health insurance", "13th month salary"],
  "is_remote": false,
  "is_active": true,
  "crawled_at": "2026-01-03T10:30:00"
}
```

---

## 🔄 Extending the Project

### Adding a New Crawler

1. Create a new file in `src/crawlers/`:

```python
# src/crawlers/my_crawler.py
from .base_crawler import BaseCrawler

class MyCrawler(BaseCrawler):
    BASE_URL = "https://example.com"

    def __init__(self, **kwargs):
        super().__init__(source="mysite", **kwargs)

    def crawl(self, **kwargs):
        """Implement crawl logic."""
        # Your crawling code here
        yield job_data

    def parse_item(self, raw_data):
        """Parse raw HTML/JSON to structured data."""
        return {
            "title": ...,
            "company_name": ...,
            # ...
        }
```

2. Register in `src/crawlers/__init__.py`:

```python
from .my_crawler import MyCrawler

CRAWLERS = {
    "itviec": ITViecCrawler,
    "topdev": TopDevCrawler,
    "mysite": MyCrawler,  # Add here
}
```

### Adding New Data Fields

1. Update `src/schemas/job.py` - Add Pydantic field
2. Update `src/database/models/job/job.py` - Add SQLAlchemy column
3. Run database migration or recreate tables

---

## 🏗️ Building Other Processes

All data mining processes are organized inside the `src/` folder. Here's how to extend the project:

### 📌 Target Project Structure

```
Data-mining-project/
│
├── api/                          # API Layer (existing)
│   ├── main.py
│   ├── models.py
│   ├── crawler_service.py
│   └── dashboard.py
│
├── src/                          # Core Source Code
│   │
│   ├── crawlers/                 # ✅ Stage 1: Data Collection (DONE)
│   │   ├── __init__.py
│   │   ├── base_crawler.py
│   │   ├── itviec_crawler.py
│   │   ├── topdev_crawler.py
│   │   └── linkedin_crawler.py
│   │
│   ├── processing/               # 🔧 Stage 2: Data Processing (TODO)
│   │   ├── __init__.py
│   │   ├── cleaner.py            # Remove duplicates, fix encoding
│   │   ├── normalizer.py         # Standardize locations, salaries
│   │   ├── skill_extractor.py    # NLP-based skill extraction
│   │   └── enricher.py           # Add derived fields
│   │
│   ├── analysis/                 # 🔧 Stage 3: Data Analysis (TODO)
│   │   ├── __init__.py
│   │   ├── statistics.py         # Descriptive statistics
│   │   ├── trend_analyzer.py     # Time-series analysis
│   │   └── skill_clustering.py   # Skill similarity analysis
│   │
│   ├── models/                   # 🔧 Stage 4: ML Models (TODO)
│   │   ├── __init__.py
│   │   ├── base_model.py         # Abstract base for ML models
│   │   ├── salary_predictor.py   # Salary prediction model
│   │   ├── job_classifier.py     # Job category classification
│   │   └── skill_recommender.py  # Skill recommendation system
│   │
│   ├── database/                 # Database Layer (existing)
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   └── models/
│   │
│   └── schemas/                  # Pydantic Schemas (existing)
│       ├── __init__.py
│       └── job.py
│
├── data/                         # Data Storage
│   ├── raw/                      # Raw crawled data
│   ├── processed/                # Cleaned data
│   ├── models/                   # Trained model files (.pkl, .joblib)
│   └── skill_dictionaries/       # Reference data
│
├── notebooks/                    # 🔧 Jupyter Notebooks (TODO)
│   ├── exploration.ipynb         # Data exploration
│   ├── training.ipynb            # Model training experiments
│   └── evaluation.ipynb          # Model evaluation
│
└── scripts/                      # 🔧 Utility Scripts (TODO)
    ├── run_processing.py         # Run data processing pipeline
    ├── train_models.py           # Train all ML models
    └── export_data.py            # Export data for dashboard
```

### 📝 Guidelines for Each Process

#### Stage 2: Data Processing (`src/processing/`)

```python
# src/processing/cleaner.py

from sqlalchemy.orm import Session
from src.database import get_db_session
from src.database.models.job import Job

class DataCleaner:
    """Clean and deduplicate job data."""

    def remove_duplicates(self, session: Session):
        """Remove duplicate jobs based on source_url."""
        # Implementation
        pass

    def normalize_locations(self, session: Session):
        """Standardize location names."""
        location_mapping = {
            "HCM": "Ho Chi Minh",
            "Hồ Chí Minh": "Ho Chi Minh",
            "HCMC": "Ho Chi Minh",
        }
        # Implementation
        pass

    def fix_encoding(self, session: Session):
        """Fix encoding issues in text fields."""
        pass
```

```python
# src/processing/skill_extractor.py

import re
from typing import List, Set

class SkillExtractor:
    """Extract skills from job descriptions using NLP."""

    def __init__(self, skill_dictionary_path: str = "data/skill_dictionaries/"):
        self.skills_db = self._load_skill_dictionary(skill_dictionary_path)

    def extract_skills(self, text: str) -> List[str]:
        """Extract skills from text using pattern matching and NLP."""
        # Use spaCy, NLTK, or custom NER
        pass

    def categorize_skills(self, skills: List[str]) -> dict:
        """Categorize skills into groups (languages, frameworks, tools)."""
        pass
```

#### Stage 3: Data Analysis (`src/analysis/`)

```python
# src/analysis/trend_analyzer.py

import pandas as pd
from datetime import datetime, timedelta
from src.database import get_db_session
from src.database.models.job import Job

class TrendAnalyzer:
    """Analyze job market trends over time."""

    def get_skill_trends(self, days: int = 30) -> pd.DataFrame:
        """Analyze which skills are trending up/down."""
        pass

    def get_salary_trends(self, by: str = "location") -> pd.DataFrame:
        """Analyze salary trends by location, skill, or level."""
        pass

    def get_demand_forecast(self, skill: str) -> dict:
        """Forecast future demand for a skill."""
        pass
```

#### Stage 4: ML Models (`src/models/`)

```python
# src/models/base_model.py

from abc import ABC, abstractmethod
from pathlib import Path
import joblib

class BaseModel(ABC):
    """Abstract base class for ML models."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = None
        self.model_path = Path(f"data/models/{model_name}.joblib")

    @abstractmethod
    def train(self, X, y):
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X):
        """Make predictions."""
        pass

    def save(self):
        """Save model to disk."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, self.model_path)

    def load(self):
        """Load model from disk."""
        if self.model_path.exists():
            self.model = joblib.load(self.model_path)
```

```python
# src/models/salary_predictor.py

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from .base_model import BaseModel
from src.database import get_db_session
from src.database.models.job import Job

class SalaryPredictor(BaseModel):
    """Predict salary based on job features."""

    def __init__(self):
        super().__init__("salary_predictor")
        self.encoders = {}

    def load_training_data(self) -> pd.DataFrame:
        """Load jobs with salary data from database."""
        with get_db_session() as session:
            jobs = session.query(Job).filter(
                Job.salary_min.isnot(None),
                Job.salary_max.isnot(None)
            ).all()
            return pd.DataFrame([{
                'title': j.title,
                'location': j.location,
                'level': j.level,
                'skills': j.required_skills,
                'salary_avg': (j.salary_min + j.salary_max) / 2
            } for j in jobs])

    def train(self, X, y):
        """Train the salary prediction model."""
        self.model = RandomForestRegressor(n_estimators=100)
        self.model.fit(X, y)
        self.save()

    def predict(self, job_features: dict) -> float:
        """Predict salary for a job."""
        # Feature preprocessing and prediction
        pass
```

### 📊 Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           Data-mining-project                                 │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐   │
│  │  CRAWLERS   │───▶│ PROCESSING  │───▶│  ANALYSIS   │───▶│   MODELS    │   │
│  │ src/crawlers│    │src/processing│   │src/analysis │    │ src/models  │   │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘   │
│         │                  │                  │                  │          │
│         ▼                  ▼                  ▼                  ▼          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         DATABASE (MySQL)                             │    │
│  │                      src/database/models/                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                           API (FastAPI)                              │    │
│  │                              api/                                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │   Datamining-dashboard (React)  │
                    └─────────────────────────────────┘
```

### 🔧 Tips for Building New Processes

1. **Follow the existing patterns** - Use Pydantic for validation, SQLAlchemy for ORM
2. **Reuse database connection** - Import from `src.database`
3. **Store models in `data/models/`** - Use joblib or pickle for serialization
4. **Add new dependencies to `requirements.txt`** - e.g., scikit-learn, spacy, nltk
5. **Create API endpoints** - Add routes in `api/` for new functionality
6. **Write tests** - Add tests in `tests/` for new modules

---

## 🧪 Testing

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov=api
```

---

## 📄 License

This project is for educational and research purposes.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## 📧 Contact

For questions or suggestions, please open an issue in this repository.
