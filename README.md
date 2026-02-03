# 🕷️ Data Mining Project - Job Crawler & Analysis System

A comprehensive data mining pipeline for collecting, processing, and analyzing IT job postings from Vietnamese job platforms. This project demonstrates end-to-end data mining workflows from web scraping to machine learning.

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [Data Pipeline](#-data-pipeline)
- [API Reference](#-api-reference)
- [Notebooks](#-notebooks)
- [Database Schema](#-database-schema)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 Overview

This project implements a complete data mining pipeline for job market analysis:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          DATA MINING PIPELINE                                    │
├─────────────────┬─────────────────┬─────────────────┬──────────────────────────┤
│   1. COLLECT    │   2. PROCESS    │   3. ANALYZE    │      4. VISUALIZE        │
├─────────────────┼─────────────────┼─────────────────┼──────────────────────────┤
│ • Web Crawlers  │ • Data Cleaning │ • Skill Extract │ • Dashboard API          │
│ • Anti-bot      │ • Translation   │ • Experience    │ • Statistics             │
│ • Multi-source  │ • Normalization │ • Clustering    │ • Trends                 │
│ • MySQL Storage │ • Deduplication │ • Scoring       │ • Insights               │
└─────────────────┴─────────────────┴─────────────────┴──────────────────────────┘
```

### Supported Platforms

| Platform                         | Status     | Features                                         |
| -------------------------------- | ---------- | ------------------------------------------------ |
| [ITViec](https://itviec.com)     | ✅ Active  | Playwright automation, cookie auth, full details |
| [TopCV](https://topcv.vn)        | ✅ Active  | CloudScraper, anti-bot bypass                    |
| [TopDev](https://topdev.vn)      | ✅ Active  | Basic crawling                                   |
| [LinkedIn](https://linkedin.com) | 🔧 Limited | FlareSolverr integration                         |

---

## ✨ Features

### Data Collection

- 🕷️ **Multi-source crawling** - 4 major Vietnamese job platforms
- 🤖 **Anti-bot solutions** - FlareSolverr, CloudScraper, Playwright
- 🔐 **Cookie authentication** - Secure session management
- ⚡ **Rate limiting** - Configurable delays to avoid detection
- 📦 **Structured storage** - MySQL with SQLAlchemy ORM

### Data Processing

- 🧹 **Data cleaning** - Remove duplicates, fix encoding issues
- 🌐 **Translation** - Vietnamese to English using Google Translator
- 📊 **Skill extraction** - 600+ technical skills from requirements
- 📅 **Experience parsing** - Min/max years from job descriptions
- 🏷️ **Job metadata** - Level, type, salary, benefits extraction

### Analysis & ML

- 📈 **Trend analysis** - Skill demand over time
- 🎯 **Job scoring** - Potential scoring based on multiple factors
- 🔍 **Skill clustering** - Group similar skills using TF-IDF
- 💰 **Salary insights** - Statistics by location, level, skills

### API & Services

- 🚀 **RESTful API** - FastAPI with async support
- 📊 **Dashboard endpoints** - Statistics and job listings
- ⚙️ **Background jobs** - Async crawl task management
- 🔍 **Search & filter** - Query jobs by multiple criteria

---

## 🏗️ Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                         USER LAYER                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │   API       │  │  Notebooks  │  │   Scripts   │           │
│  │ (FastAPI)   │  │  (Jupyter)  │  │  (Python)   │           │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘           │
└─────────┼─────────────────┼─────────────────┼─────────────────┘
          │                 │                 │
┌─────────┼─────────────────┼─────────────────┼─────────────────┐
│         │        SERVICE LAYER               │                 │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌───────▼──────┐          │
│  │  Crawlers   │  │ Processing  │  │   Analysis   │          │
│  │  (4 sites)  │  │  Pipeline   │  │   Engine     │          │
│  └──────┬──────┘  └──────┬──────┘  └───────┬──────┘          │
└─────────┼─────────────────┼─────────────────┼─────────────────┘
          │                 │                 │
┌─────────┼─────────────────┼─────────────────┼─────────────────┐
│         │         DATA LAYER                 │                 │
│  ┌──────▼──────────────────▼─────────────────▼──────┐         │
│  │              MySQL Database (TiDB Cloud)          │         │
│  │  Tables: jobs, jobs_it, crawl_logs, metadata    │         │
│  └───────────────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

### Core Technologies

- **Python 3.11+** - Main programming language
- **FastAPI** - Modern async web framework
- **SQLAlchemy** - ORM for database operations
- **Playwright** - Browser automation
- **MySQL 8.0** - Database (TiDB Cloud)

### Data Processing

- **Pandas** - Data manipulation and analysis
- **NumPy** - Numerical computing
- **Scikit-learn** - Machine learning (TF-IDF, clustering)
- **Deep-Translator** - Language translation
- **LangDetect** - Language detection

### Web Scraping

- **BeautifulSoup4** - HTML parsing
- **Requests** - HTTP library
- **CloudScraper** - Anti-bot bypass
- **FlareSolverr** - Cloudflare bypass

### Development Tools

- **Docker** - Containerization
- **Pytest** - Testing framework
- **Jupyter** - Interactive notebooks
- **Git** - Version control

---

## 📁 Project Structure

```
Data-mining-project/
│
├── api/                          # FastAPI Application
│   ├── main.py                   # API entry point
│   ├── models.py                 # Pydantic models
│   ├── crawler_service.py        # Crawler management
│   └── dashboard.py              # Dashboard endpoints
│
├── config/                       # Configuration
│   └── setting.py                # Environment settings
│
├── src/                          # Core Source Code
│   ├── crawlers/                 # Web Crawlers
│   │   ├── base_crawler.py       # Abstract base
│   │   ├── itviec_crawler.py     # ITViec implementation
│   │   ├── topdev_crawler.py     # TopDev implementation
│   │   ├── topcv_crawler.py      # TopCV implementation
│   │   └── linkedin_crawler.py   # LinkedIn implementation
│   │
│   ├── database/                 # Database Layer
│   │   ├── connection.py         # DB connection & session
│   │   └── models/               # ORM models
│   │       └── job/
│   │           ├── job.py        # Job model
│   │           ├── job_it.py     # IT-specific fields
│   │           └── crud_job.py   # CRUD operations
│   │
│   └── schemas/                  # Pydantic Schemas
│       └── job.py                # Job validation
│
├── notebooks/                    # Jupyter Notebooks
│   ├── extract_experience_years.ipynb
│   ├── extract_skills_from_requirements.ipynb
│   ├── extract_job_metadata.ipynb
│   ├── translate_job_titles.ipynb
│   ├── translate_jobs_data.ipynb
│   ├── check_empty_experience_years.ipynb
│   ├── fix_unreasonable_experience_years.ipynb
│   └── fill_job_type_and_level.ipynb
│
├── data/                         # Data Storage
│   ├── raw/                      # Raw crawled data
│   ├── processed/                # Cleaned data
│   └── skill_dictionaries/       # Skill reference data
│
├── certs/                        # SSL Certificates
│   └── README.md
│
├── tests/                        # Test Suite
│   └── test_api.py
│
├── docker-compose.yml            # Docker orchestration
├── Dockerfile                    # Container definition
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── init_db.py                    # Database initialization
├── linkedin_crawler_best.py      # Standalone LinkedIn crawler
├── DATA_MINING_PIPELINE.md       # Detailed pipeline docs
└── README.md                     # This file
```

---

## 🚀 Installation

### Prerequisites

- Python 3.11+
- MySQL 8.0+ or TiDB Cloud account
- Docker & Docker Compose (optional)
- 4GB+ RAM recommended

### Option 1: Local Development

```bash
# Clone repository
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

# Set up environment
cp .env.example .env
# Edit .env with your database credentials

# Initialize database
python init_db.py

# Run API server
python -m uvicorn api.main:app --reload --port 8000
```

### Option 2: Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

---

## ⚙️ Configuration

Create a `.env` file with the following variables:

```env
# Database Configuration
MYSQL_HOST=gateway01.ap-southeast-1.prod.aws.tidbcloud.com
MYSQL_PORT=4000
MYSQL_DATABASE=data-mining
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password

# SSL Configuration (for TiDB Cloud)
DB_SSL_ENABLED=true
DB_SSL_CA=/path/to/ca-cert.pem

# Application Settings
DEBUG=false
LOG_LEVEL=INFO

# Crawler Settings
CRAWLER_DELAY_MIN=2
CRAWLER_DELAY_MAX=5
MAX_RETRIES=3
```

---

## 📖 Usage

### 1. Start API Server

```bash
python -m uvicorn api.main:app --reload --port 8000
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### 2. Trigger Crawl Job

```bash
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
```

### 3. Check Job Status

```bash
curl "http://localhost:8000/api/v1/jobs/{job_id}"
```

### 4. Get Dashboard Data

```bash
# Get all jobs
curl "http://localhost:8000/api/v1/dashboard/jobs?limit=100"

# Get statistics
curl "http://localhost:8000/api/v1/dashboard/stats"
```

### 5. Use Crawlers Directly

```python
from src.crawlers import create_crawler

# Create crawler
crawler = create_crawler(
    source="itviec",
    cookies_path="itviec-session-cookies.json",
    headless=True
)

# Run crawl
for job in crawler.crawl(keywords=["python"], pages=3):
    print(f"Found: {job['title']} at {job['company_name']}")
```

---

## 🔄 Data Pipeline

### Stage 1: Data Collection

- Crawl job postings from multiple sources
- Extract 25+ fields per job
- Store raw data in MySQL
- Handle anti-bot measures

### Stage 2: Data Processing

- **Translation** - Convert Vietnamese text to English
- **Skill Extraction** - Identify 600+ technical skills
- **Experience Parsing** - Extract years of experience
- **Metadata Extraction** - Education, certifications, job type
- **Data Quality** - Fill missing values, fix inconsistencies

### Stage 3: Data Analysis

- **Skill Clustering** - Group similar skills using TF-IDF
- **Trend Analysis** - Track skill demand over time
- **Salary Analysis** - Statistics by location and level
- **Job Scoring** - Rank jobs by multiple factors

### Stage 4: Insights Generation

- Top demanded skills
- Salary trends by location
- Experience requirements by level
- Most common benefits

---

## 🔌 API Reference

### Core Endpoints

| Endpoint                | Method | Description          |
| ----------------------- | ------ | -------------------- |
| `/`                     | GET    | API information      |
| `/health`               | GET    | Health check         |
| `/api/v1/sources`       | GET    | List crawler sources |
| `/api/v1/crawl`         | POST   | Start crawl job      |
| `/api/v1/jobs/{job_id}` | GET    | Get job status       |
| `/api/v1/jobs`          | GET    | List all crawl jobs  |

### Dashboard Endpoints

| Endpoint                    | Method | Description            |
| --------------------------- | ------ | ---------------------- |
| `/api/v1/dashboard/jobs`    | GET    | Get jobs from database |
| `/api/v1/dashboard/stats`   | GET    | Get statistics         |
| `/api/v1/dashboard/sources` | GET    | Jobs by source         |
| `/api/v1/dashboard/skills`  | GET    | Top skills             |

### Example Request

```bash
POST /api/v1/crawl
{
  "source": "itviec",
  "keywords": ["python", "django"],
  "location": "ha-noi",
  "pages": 10,
  "max_jobs": 200,
  "fetch_details": true,
  "store_to_db": true
}
```

---

## 📓 Notebooks

### Data Processing Notebooks

1. **[extract_experience_years.ipynb](notebooks/extract_experience_years.ipynb)**
   - Extract min/max years of experience from job descriptions
   - Pattern matching with regex
   - Fallback to job level inference

2. **[extract_skills_from_requirements.ipynb](notebooks/extract_skills_from_requirements.ipynb)**
   - Extract 600+ technical skills from requirements
   - Categorize by type (languages, frameworks, tools)
   - Store as JSON array in database

3. **[extract_job_metadata.ipynb](notebooks/extract_job_metadata.ipynb)**
   - Extract education requirements
   - Identify certifications
   - Parse job type and level information

4. **[translate_job_titles.ipynb](notebooks/translate_job_titles.ipynb)**
   - Translate Vietnamese job titles to English
   - Language detection with fallback
   - Batch processing with caching

5. **[translate_jobs_data.ipynb](notebooks/translate_jobs_data.ipynb)**
   - Translate all text fields (description, requirements, benefits)
   - Handle Vietnamese administrative terms for locations
   - Skip LinkedIn jobs (already in English)
   - Progress tracking with statistics

6. **[check_empty_experience_years.ipynb](notebooks/check_empty_experience_years.ipynb)**
   - Data quality analysis for experience years
   - Identify missing or NULL values
   - Generate visualizations and statistics

7. **[fix_unreasonable_experience_years.ipynb](notebooks/fix_unreasonable_experience_years.ipynb)**
   - Fill missing experience years values
   - Use job level to infer reasonable ranges
   - Update database with filled values

8. **[fill_job_type_and_level.ipynb](notebooks/fill_job_type_and_level.ipynb)**
   - Detect job_type from title and description
   - Detect job level (Intern, Junior, Senior, etc.)
   - Handle "all" level values and fill with specific levels

---

## 🗄️ Database Schema

### `jobs` Table

```sql
CREATE TABLE jobs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    title VARCHAR(500),
    company_name VARCHAR(255),
    location TEXT,
    source VARCHAR(50),
    source_url TEXT UNIQUE,
    description TEXT,
    requirements_text TEXT,
    job_type VARCHAR(100),
    level VARCHAR(100),
    salary_min DECIMAL(15, 2),
    salary_max DECIMAL(15, 2),
    salary_currency VARCHAR(10),
    experience_years_min INT,
    experience_years_max INT,
    education_level VARCHAR(255),
    required_skills JSON,
    preferred_skills JSON,
    certifications JSON,
    benefits JSON,
    is_remote BOOLEAN,
    is_active BOOLEAN,
    posted_date DATE,
    crawled_at TIMESTAMP,
    updated_at TIMESTAMP,

    INDEX idx_source (source),
    INDEX idx_location (location(255)),
    INDEX idx_level (level),
    INDEX idx_posted (posted_date),
    FULLTEXT INDEX ft_description (description, requirements_text)
);
```

### Key Features

- **JSON columns** for flexible skill/benefit storage
- **Full-text search** on description and requirements
- **Indexes** on source, location, level, posted_date for fast queries
- **Unique constraint** on source_url for automatic deduplication
- **Timestamp tracking** for crawl and update times

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov=api --cov-report=html

# Run specific test
pytest tests/test_api.py::test_root -v
```

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add docstrings to all functions
- Write tests for new features
- Update documentation as needed

---

## 📄 License

This project is for educational and research purposes. Please respect the terms of service of the scraped websites.

---

## 📧 Contact

For questions or suggestions, please open an issue in this repository.

---

## 🙏 Acknowledgments

- **Data sources**: ITViec, TopCV, TopDev, LinkedIn
- **FlareSolverr** for Cloudflare bypass solutions
- **TiDB Cloud** for MySQL-compatible database hosting
- **FastAPI** framework for modern API development
- **Playwright** for reliable browser automation

---

## 🎓 Educational Use

This project demonstrates:

- Web scraping techniques and anti-bot solutions
- Data cleaning and normalization workflows
- Natural language processing for skill extraction
- RESTful API design with FastAPI
- Database design and optimization
- Docker containerization
- Data analysis with Jupyter notebooks

**Built with ❤️ for the Data Mining community**
