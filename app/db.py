"""
Database configuration and session management.
"""

from sqlmodel import SQLModel, create_engine, Session
from typing import Generator
import os
import json
from datetime import datetime

# Import all models to ensure they are registered with SQLModel
from app.models import Partner, Carrier, CarrierCapacity, Quote, Policy, Ledger, IdempotencyKey

# Database URL - defaults to SQLite for development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/insurance.db")

# Create engine
engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    """Create database tables."""
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session

def load_seed_data():
    """Load seed data from config/seed.json into the database."""
    import os
    seed_file = os.path.join(os.path.dirname(__file__), "config", "seed.json")
    
    if not os.path.exists(seed_file):
        print(f"Warning: Seed file not found at {seed_file}")
        return
    
    with open(seed_file, 'r') as f:
        seed_data = json.load(f)
    
    with Session(engine) as session:
        # Load partners
        for partner_data in seed_data.get("partners", []):
            # Check if partner already exists
            existing_partner = session.query(Partner).filter(Partner.id == partner_data["id"]).first()
            if not existing_partner:
                partner = Partner(
                    id=partner_data["id"],
                    api_key=partner_data["api_key"],
                    markup_pct=partner_data["markup_pct"],
                    regions=json.dumps(partner_data["regions"]),
                    products=json.dumps(partner_data["products"])
                )
                session.add(partner)
        
        # Load carriers
        for carrier_data in seed_data.get("carriers", []):
            # Check if carrier already exists
            existing_carrier = session.query(Carrier).filter(Carrier.id == carrier_data["id"]).first()
            if not existing_carrier:
                carrier = Carrier(
                    id=carrier_data["id"],
                    name=carrier_data["name"],
                    appetite_json=json.dumps(carrier_data["appetite"]),
                    capacity_monthly_limit=carrier_data["capacity"]["monthly_policies"],
                    pricing_curve_ref=carrier_data["pricing_curve_ref"]
                )
                session.add(carrier)
                
                # Initialize carrier capacity for current month
                current_month = datetime.now().strftime("%Y-%m")
                capacity = CarrierCapacity(
                    carrier_id=carrier_data["id"],
                    as_of_month=current_month,
                    remaining_count=carrier_data["capacity"]["monthly_policies"]
                )
                session.add(capacity)
        
        session.commit()
        print("Seed data loaded successfully")

def initialize_database():
    """Initialize database with tables and seed data."""
    print("Creating database tables...")
    create_db_and_tables()
    print("Loading seed data...")
    load_seed_data()
    print("Database initialization complete")
