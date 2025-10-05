# Embedded Insurance API

A FastAPI-based insurance API for embedded insurance products including shipping insurance and payment protection insurance (PPI). Built for BNPL marketplaces to quote and bind insurance policies.

## Features

- **Shipping Insurance**: Coverage for packages with risk-based pricing
- **Payment Protection Insurance (PPI)**: Coverage for payment transactions
- **Compliance Engine**: YAML-based rules engine for regulatory compliance
- **Risk Scoring**: Deterministic risk assessment with A-E bands
- **Carrier Routing**: Intelligent carrier selection based on appetite and capacity
- **Portfolio Simulation**: Monte Carlo simulation with VaR/TailVaR calculations
- **High Performance**: Sub-25ms p50 response times (10x better than 250ms target)

## Prerequisites

- **Docker** and **Docker Compose**
- **Git** (for cloning)

## Quick Start with Docker

### 1. Clone and Setup or Extract folder from zip

```bash
git clone <repository-url>
cd Corgi
```

### 2. Build and Start

```bash
# Build Docker image
docker compose build

# Start the API server (automatically loads seed data)
docker compose up -d

# Generate test policies data
docker compose exec api python3 app/data/generate_policies.py
```

### 3. Verify Setup

```bash
# Check if API is running
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","version":"1.0.0"}
```

### 4. Run Tests

```bash
# Run all tests in Docker
docker compose exec api bash -c "PYTHONPATH=/app pytest tests/ -v"

# Expected: 49 tests passing
```

### 5. Performance Testing

```bash
# Run performance test (100 requests)
docker compose exec api python3 test_performance.py
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/v1/quotes` | Get insurance quotes |
| `POST` | `/v1/bindings` | Bind quotes to policies |
| `GET` | `/v1/policies/{id}` | Retrieve policy details |
| `POST` | `/v1/portfolio/simulate` | Run portfolio simulations |

## Available API Keys

| Key | Partner | Products | Markup |
|-----|---------|----------|--------|
| `KLARITY_TEST_KEY` | ptnr_klarity | shipping, ppi | 8% |
| `AFTERDAY_TEST_KEY` | ptnr_afterday | shipping, ppi | 5% |

## API Examples

### 1. Shipping Insurance Quote

```bash
curl -X POST http://localhost:8000/v1/quotes \
  -H "Authorization: Bearer KLARITY_TEST_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "product_code": "shipping",
    "shipping": {
      "declared_value": 65000,
      "item_category": "electronics",
      "destination_state": "CA",
      "destination_risk": "medium",
      "service_level": "ground"
    }
  }'
```

**Response:**
```json
{
  "quote_id": 1,
  "product_code": "shipping",
  "premium_cents": 62162,
  "price_breakdown": {
    "base_premium_cents": 57558,
    "risk_multiplier": 1.4,
    "partner_markup_pct": 0.08,
    "total_premium_cents": 62162
  },
  "risk_band": "E",
  "risk_multiplier": 1.4,
  "carrier_suggestion": "c_atlas",
  "router_rationale": "Selected c_atlas with margin $99.46 (premium: $621.62, capacity: 20000)",
  "compliance": {
    "decision": "allow",
    "disclosures": ["High value shipment - additional documentation may be required"],
    "rules_applied": ["shipping_high_value_disclosure"],
    "version": "1.0"
  }
}
```

### 2. PPI Insurance Quote

```bash
curl -X POST http://localhost:8000/v1/quotes \
  -H "Authorization: Bearer KLARITY_TEST_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "product_code": "ppi",
    "ppi": {
      "order_value": 45000,
      "term_months": 12,
      "job_category": "full_time"
    }
  }'
```

### 3. Bind Quote to Policy

```bash
curl -X POST http://localhost:8000/v1/bindings \
  -H "Authorization: Bearer KLARITY_TEST_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "quote_id": 1,
    "policyholder": {
      "name": "A Lee",
      "age": 29,
      "state": "CA",
      "email": "a@x.com",
      "tenure_months": 12
    }
  }'
```

**Response:**
```json
{
  "policy_id": 1,
  "status": "active",
  "premium_total_cents": 62162,
  "carrier_id": "c_atlas",
  "effective_date": "2025-10-04"
}
```

### 4. Retrieve Policy Details

```bash
curl -X GET http://localhost:8000/v1/policies/1 \
  -H "Authorization: Bearer KLARITY_TEST_KEY"
```

### 5. Portfolio Simulation

```bash
curl -X POST http://localhost:8000/v1/portfolio/simulate \
  -H "Authorization: Bearer KLARITY_TEST_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "as_of_month": "2025-08",
    "scenario_count": 2000,
    "retention_grid": [50000, 100000, 250000, 500000, 1000000],
    "reinsurance_params": {
      "rate_on_line": 0.20,
      "load": 0.10
    }
  }'
```

**Response:**
```json
{
  "var95": 33133.05,
  "var99": 21157.35,
  "tailvar99": 68996.92,
  "retention_table": [
    {
      "retention": 50000.0,
      "expected_loss": 47506.92,
      "expected_ceded": 20929.69,
      "reinsurance_premium": 4604.53,
      "expected_net": 52111.45
    }
  ],
  "recommended": {
    "retention": 50000.0,
    "expected_net": 52111.45,
    "rationale": "Minimum expected net cost of $52111.45"
  }
}
```

### 6. Compliance Block Example

```bash
# This will be blocked due to GA state restriction
curl -X POST http://localhost:8000/v1/bindings \
  -H "Authorization: Bearer KLARITY_TEST_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "quote_id": 3,
    "policyholder": {
      "name": "Test User",
      "age": 29,
      "state": "GA",
      "email": "test@example.com",
      "tenure_months": 12
    }
  }'
```

**Response (400):**
```json
{
  "detail": "Binding blocked by compliance: ppi_ga_block, ban_ppi_states"
}
```

## Database Workflow

The API automatically loads seed data on startup:

### Automatic Seed Data Loading
- **Tables created**: Partners, Carriers, Quotes, Policies, Ledger, etc.
- **Seed data loaded**: Partners, carriers, and pricing curves loaded automatically
- **Ready to use**: API is immediately functional after startup

### Additional Test Data
```bash
# Generate test policies (20,000 synthetic policies)
docker compose exec api python3 app/data/generate_policies.py
```

## Project Structure

```
app/
├── main.py              # FastAPI application
├── deps.py              # Dependencies and middleware
├── db.py                # Database configuration
├── models.py            # SQLModel database models
├── schemas.py           # Pydantic request/response schemas
├── cache.py             # Configuration caching
├── middleware.py        # Performance and request middleware
├── routers/             # API route handlers
│   ├── quotes.py        # Quote endpoint
│   ├── bindings.py      # Binding endpoint
│   ├── policies.py      # Policy retrieval
│   └── portfolio.py     # Portfolio simulation
├── services/            # Business logic services
│   ├── risk.py          # Risk scoring
│   ├── pricing.py       # Premium calculation
│   ├── routing.py       # Carrier selection
│   ├── compliance.py    # Compliance engine
│   ├── ledger.py        # Ledger management
│   └── simulate.py      # Portfolio simulation
├── config/              # Configuration files
│   ├── seed.json        # Partners, carriers, pricing
│   └── compliance.yaml  # Compliance rules
└── data/                # Data generation scripts
    └── generate_policies.py
```

## Configuration Files

### `config/seed.json`
Contains partners, carriers, and pricing curves exactly as specified in requirements.

### `config/compliance.yaml`
YAML-based compliance rules engine with blocking and disclosure rules.

### `data/generate_policies.py`
Generates 20,000 synthetic policies deterministically for testing.

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs

## Troubleshooting

### Common Issues

1. **Container won't start:**
```bash
# Check logs
docker compose logs api

# Rebuild if needed
docker compose down
docker compose build --no-cache
docker compose up -d
```

2. **Port 8000 in use:**
```bash
# Find and kill process
lsof -ti:8000 | xargs kill -9
```

3. **Authentication errors:**
```bash
# Use correct API key
curl -H "Authorization: Bearer KLARITY_TEST_KEY" ...
```

4. **Database issues:**
```bash
# Reset everything
docker compose down -v
docker compose up -d
docker compose exec api python3 app/data/generate_policies.py
```

## Development

### Making Changes

1. **Edit code** in your local files
2. **Restart container** to pick up changes:
   ```bash
   docker compose restart api
   ```
3. **Run tests** to verify:
   ```bash
   docker compose exec api bash -c "PYTHONPATH=/app pytest tests/ -v"
   ```

### Adding New Features

1. **Add tests** in `tests/` directory
2. **Update schemas** in `app/schemas.py`
3. **Add routes** in `app/routers/`
4. **Implement business logic** in `app/services/`
5. **Run tests** to verify functionality

## Monitoring

The API includes built-in monitoring with request tracing, performance monitoring, health checks, and structured logging.

```bash
# Health check
curl http://localhost:8000/health

# Check logs
docker compose logs -f api
```

## Production Deployment

For production deployment, modify the existing `docker-compose.yml`:

### Production Configuration

Modify your `docker-compose.yml`:
```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data  # Keep data volume for SQLite database
    environment:
      - ENV=production
      - DATABASE_URL=sqlite:///./data/insurance.db
    restart: unless-stopped
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000  # Remove --reload
```

### Production Considerations

1. **Database**: Uses SQLite (as designed) - ensure data volume is backed up
2. **Environment**: Set `ENV=production` 
3. **Remove Development Features**: Remove `--reload` flag
4. **Data Persistence**: The `./data:/app/data` volume ensures SQLite database persists
5. **Reverse Proxy**: Use nginx for SSL termination and load balancing
6. **Monitoring**: Use the built-in performance metrics
7. **Backup**: Regularly backup the `./data/insurance.db` file

### Production Commands

```bash
# Build and start production services
docker compose build
docker compose up -d

# Health check
curl http://localhost:8000/health
```
