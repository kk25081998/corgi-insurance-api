"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import initialize_database
from app.routers import quotes, bindings, policies, portfolio
from app.middleware import PerformanceMiddleware, RequestContextMiddleware
from app.cache import config_cache
import logging

# Configure logging
logger = logging.getLogger("embedded_insurance")

app = FastAPI(
    title="Embedded Insurance API",
    description="API for embedded insurance products including shipping and PPI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add performance middleware (innermost - executes first)
app.add_middleware(PerformanceMiddleware)

# Add request context middleware
app.add_middleware(RequestContextMiddleware)

# Add CORS middleware (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize database and warm up caches on startup."""
    logger.info("Starting Embedded Insurance API...")
    
    # Initialize database
    initialize_database()
    logger.info("Database initialized")
    
    # Warm up config cache
    config_cache.get_seed_data()
    logger.info(f"Config cache warmed up: {len(config_cache.get_carriers())} carriers, "
                f"{len(config_cache.get_partners())} partners")
    
    logger.info("Startup complete")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Embedded Insurance API", "status": "healthy"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

# Include all routers
app.include_router(quotes.router, prefix="/v1", tags=["quotes"])
app.include_router(bindings.router, prefix="/v1", tags=["bindings"])
app.include_router(policies.router, prefix="/v1", tags=["policies"])
app.include_router(portfolio.router, prefix="/v1", tags=["portfolio"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
