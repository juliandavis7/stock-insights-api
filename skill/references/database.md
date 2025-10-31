# Database Reference

Database configuration and schema information.

## Current Status

**Database: Not Yet Implemented**

The API currently does not use a persistent database. All data is fetched from external APIs (FMP and yfinance) on-demand.

## Future Implementation Plans

### Potential Use Cases

1. **User Data Storage**
   - User preferences
   - Saved watchlists
   - Custom projection templates
   - API usage tracking

2. **Caching Layer**
   - Cache FMP API responses
   - Reduce external API calls
   - Improve response times
   - Store historical calculations

3. **Analytics & Monitoring**
   - Track endpoint usage
   - Monitor rate limit hits
   - Store error logs
   - User activity analytics

### Recommended Stack

**PostgreSQL + SQLAlchemy**

Rationale:
- Robust relational database
- Good Python integration
- JSON support for flexible data
- Strong data integrity
- Scalable

Alternative:
- **Redis** - For caching and rate limiting (already planned for rate limiting)

## Proposed Schema (When Implemented)

### Users Table
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    clerk_user_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    subscription_tier VARCHAR(50) DEFAULT 'free'
);
```

### Watchlists Table
```sql
CREATE TABLE watchlists (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    name VARCHAR(255),
    tickers TEXT[],  -- Array of ticker symbols
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Cache Table
```sql
CREATE TABLE api_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    endpoint VARCHAR(100),
    ticker VARCHAR(10),
    data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    INDEX idx_cache_key ON api_cache(cache_key),
    INDEX idx_expires_at ON api_cache(expires_at)
);
```

### Usage Tracking Table
```sql
CREATE TABLE usage_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    endpoint VARCHAR(100),
    ticker VARCHAR(10),
    request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_status INTEGER,
    fmp_api_calls INTEGER DEFAULT 0,
    INDEX idx_user_timestamp ON usage_logs(user_id, request_timestamp)
);
```

## SQLAlchemy Models (Proposed)

```python
# models/database.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ARRAY, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    clerk_user_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime)
    subscription_tier = Column(String(50), default='free')


class Watchlist(Base):
    __tablename__ = 'watchlists'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    name = Column(String(255))
    tickers = Column(ARRAY(String))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class APICache(Base):
    __tablename__ = 'api_cache'
    
    id = Column(Integer, primary_key=True)
    cache_key = Column(String(255), unique=True, nullable=False)
    endpoint = Column(String(100))
    ticker = Column(String(10))
    data = Column(JSON)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime)


class UsageLog(Base):
    __tablename__ = 'usage_logs'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    endpoint = Column(String(100))
    ticker = Column(String(10))
    request_timestamp = Column(DateTime, default=func.now())
    response_status = Column(Integer)
    fmp_api_calls = Column(Integer, default=0)
```

## Database Connection Setup (When Implemented)

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/stockapi')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Usage in endpoints:
```python
from database import get_db
from sqlalchemy.orm import Session

@app.get("/user/watchlists")
def get_watchlists(
    user: Dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    user_id = user.get('sub')
    watchlists = db.query(Watchlist).filter(Watchlist.user_id == user_id).all()
    return watchlists
```

## Migration Strategy (When Implemented)

Use Alembic for database migrations:

```bash
# Install
pip install alembic

# Initialize
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Create initial tables"

# Apply migration
alembic upgrade head
```

## Caching Strategy

When database is implemented, use it for intelligent caching:

```python
from datetime import datetime, timedelta

def get_cached_or_fetch(cache_key: str, fetch_func, ttl_minutes: int = 10):
    """Get data from cache or fetch and cache it."""
    # Check cache
    cached = db.query(APICache).filter(
        APICache.cache_key == cache_key,
        APICache.expires_at > datetime.now()
    ).first()
    
    if cached:
        return cached.data
    
    # Fetch fresh data
    data = fetch_func()
    
    # Store in cache
    cache_entry = APICache(
        cache_key=cache_key,
        data=data,
        expires_at=datetime.now() + timedelta(minutes=ttl_minutes)
    )
    db.add(cache_entry)
    db.commit()
    
    return data
```

## Environment Variables (When Implemented)

```bash
# PostgreSQL connection
DATABASE_URL=postgresql://user:password@localhost:5432/stockapi

# For Docker
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=stockapi
DATABASE_USER=stockapi_user
DATABASE_PASSWORD=your_secure_password
```

## Docker Setup (When Implemented)

```yaml
# docker-compose.yml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: stockapi_user
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
      POSTGRES_DB: stockapi
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

Start database:
```bash
docker-compose up -d postgres
```

## Current Workarounds

Since no database is implemented:

1. **No persistent user data** - Each request is stateless
2. **No caching** - All data fetched from external APIs
3. **Rate limiting** - Using in-memory storage (SlowAPI)
4. **No usage tracking** - Rely on logs only

## When to Implement Database

Consider implementing when:
- Need to store user preferences/watchlists
- Want to reduce FMP API calls through caching
- Need detailed analytics and usage tracking
- Scaling to multiple API instances (need shared state)
- Want to implement user tiers with different limits

## Migration Path

1. **Phase 1**: Add PostgreSQL for user data only
2. **Phase 2**: Implement API response caching
3. **Phase 3**: Add usage tracking and analytics
4. **Phase 4**: Move rate limiting to Redis + database

---

**Note**: This is planning documentation. No database is currently implemented. All data operations go directly to external APIs (FMP and yfinance).

