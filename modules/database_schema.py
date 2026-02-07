#!/usr/bin/env python3
"""
DATABASE SCHEMA - PostgreSQL Models & Queries
System 5.0.6 - Complete database layer for ReviewSignal

Author: ReviewSignal Team
Version: 5.0.6
Date: January 2026
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, JSON, ForeignKey, Index, Enum as SQLEnum,
    UniqueConstraint, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.sql import func
from typing import List, Dict, Optional, Type, TypeVar
from datetime import datetime
from enum import Enum
import structlog

logger = structlog.get_logger()

Base = declarative_base()
T = TypeVar('T', bound=Base)


# ═══════════════════════════════════════════════════════════════════
# ENUMS FOR DATABASE
# ═══════════════════════════════════════════════════════════════════

class UserStatusEnum(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BANNED = "banned"
    DELETED = "deleted"


class UserRoleEnum(str, Enum):
    VIEWER = "viewer"
    ANALYST = "analyst"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"


class SubscriptionTierEnum(str, Enum):
    TRIAL = "trial"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class PaymentStatusEnum(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class LeadStatusEnum(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


# ═══════════════════════════════════════════════════════════════════
# MODELS - USERS & AUTH
# ═══════════════════════════════════════════════════════════════════

class User(Base):
    """User account model"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRoleEnum), default=UserRoleEnum.ANALYST)
    status = Column(SQLEnum(UserStatusEnum), default=UserStatusEnum.PENDING)
    
    # Stripe integration
    stripe_customer_id = Column(String(255), unique=True, nullable=True, index=True)
    subscription_tier = Column(SQLEnum(SubscriptionTierEnum), default=SubscriptionTierEnum.TRIAL)
    
    # Usage tracking
    api_calls_used = Column(Integer, default=0)
    api_calls_limit = Column(Integer, default=100)
    reports_generated = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime, nullable=True)
    
    # Metadata
    extra_data = Column(JSON, default={})
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user")
    
    __table_args__ = (
        Index('idx_users_company', 'company'),
        Index('idx_users_status_role', 'status', 'role'),
    )
    
    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "name": self.name,
            "company": self.company,
            "role": self.role.value,
            "status": self.status.value,
            "subscription_tier": self.subscription_tier.value,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class UserSession(Base):
    """User session model"""
    __tablename__ = 'user_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.user_id'), nullable=False)
    token_hash = Column(String(255), nullable=False)
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_sessions_user_active', 'user_id', 'is_active'),
    )


class APIKey(Base):
    """API key model"""
    __tablename__ = 'api_keys'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    key_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.user_id'), nullable=False)
    key_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    permissions = Column(JSON, default=[])
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    last_used = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="api_keys")


# ═══════════════════════════════════════════════════════════════════
# MODELS - CHAINS & LOCATIONS
# ═══════════════════════════════════════════════════════════════════

class Chain(Base):
    """Restaurant chain model"""
    __tablename__ = 'chains'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chain_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), index=True)  # fast_food, casual_dining, etc.
    logo_url = Column(String(500))
    website = Column(String(500))
    
    # Stats (aggregated)
    total_locations = Column(Integer, default=0)
    avg_rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    extra_data = Column(JSON, default={})
    
    locations = relationship("Location", back_populates="chain")
    
    def to_dict(self) -> Dict:
        return {
            "chain_id": self.chain_id,
            "name": self.name,
            "category": self.category,
            "total_locations": self.total_locations,
            "avg_rating": round(self.avg_rating, 2),
            "total_reviews": self.total_reviews
        }


class Location(Base):
    """Individual location model"""
    __tablename__ = 'locations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(String(64), unique=True, nullable=False, index=True)
    place_id = Column(String(255), unique=True, index=True)  # Google Place ID
    chain_id = Column(String(64), ForeignKey('chains.chain_id'), nullable=True)
    
    # Basic info
    name = Column(String(255), nullable=False)
    address = Column(String(500))
    city = Column(String(100), index=True)
    country = Column(String(100), index=True)
    postal_code = Column(String(20))
    
    # Coordinates
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Current metrics
    current_rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    price_level = Column(Integer)  # 1-4
    
    # Status
    is_active = Column(Boolean, default=True)
    last_scraped = Column(DateTime)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    extra_data = Column(JSON, default={})
    
    chain = relationship("Chain", back_populates="locations")
    reviews = relationship("Review", back_populates="location")
    rating_history = relationship("RatingHistory", back_populates="location")
    
    __table_args__ = (
        Index('idx_locations_city_chain', 'city', 'chain_id'),
        Index('idx_locations_rating', 'current_rating'),
        Index('idx_locations_coords', 'latitude', 'longitude'),
    )
    
    def to_dict(self) -> Dict:
        return {
            "location_id": self.location_id,
            "place_id": self.place_id,
            "name": self.name,
            "address": self.address,
            "city": self.city,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "current_rating": self.current_rating,
            "review_count": self.review_count
        }


class Review(Base):
    """Individual review model"""
    __tablename__ = 'reviews'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    review_id = Column(String(64), unique=True, nullable=False, index=True)
    location_id = Column(String(64), ForeignKey('locations.location_id'), nullable=False)
    
    # Review content
    author_name = Column(String(255))
    rating = Column(Integer, nullable=False)  # 1-5
    text = Column(Text)
    language = Column(String(10))
    
    # Sentiment analysis
    sentiment_score = Column(Float)  # -1 to 1
    sentiment_label = Column(String(20))  # positive, negative, neutral
    topics = Column(JSON, default=[])  # ["food", "service", "cleanliness"]
    
    # Metadata
    review_time = Column(DateTime)
    scraped_at = Column(DateTime, server_default=func.now())
    source = Column(String(50), default="google")  # google, yelp, etc.
    
    location = relationship("Location", back_populates="reviews")
    
    __table_args__ = (
        Index('idx_reviews_location_time', 'location_id', 'review_time'),
        Index('idx_reviews_rating', 'rating'),
        Index('idx_reviews_sentiment', 'sentiment_label'),
        CheckConstraint('rating >= 1 AND rating <= 5', name='check_rating_range'),
    )


class RatingHistory(Base):
    """Historical rating data for trend analysis"""
    __tablename__ = 'rating_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    location_id = Column(String(64), ForeignKey('locations.location_id'), nullable=False)
    
    date = Column(DateTime, nullable=False)
    rating = Column(Float, nullable=False)
    review_count = Column(Integer, nullable=False)
    new_reviews = Column(Integer, default=0)
    
    location = relationship("Location", back_populates="rating_history")
    
    __table_args__ = (
        UniqueConstraint('location_id', 'date', name='uq_location_date'),
        Index('idx_rating_history_date', 'date'),
    )


# ═══════════════════════════════════════════════════════════════════
# MODELS - LEADS
# ═══════════════════════════════════════════════════════════════════

class Lead(Base):
    """LinkedIn lead model"""
    __tablename__ = 'leads'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # Person info
    full_name = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    headline = Column(String(500))
    
    # Contact
    email = Column(String(255), index=True)
    phone = Column(String(50))
    linkedin_url = Column(String(500), unique=True)
    
    # Company
    company_name = Column(String(255), index=True)
    company_linkedin_url = Column(String(500))
    job_title = Column(String(255))
    
    # Location
    location = Column(String(255))
    country = Column(String(100), index=True)
    
    # Scoring
    lead_score = Column(Integer, default=0)  # 0-100
    status = Column(SQLEnum(LeadStatusEnum), default=LeadStatusEnum.NEW)
    
    # Tracking
    source = Column(String(100))  # linkedin_search, referral, etc.
    assigned_to = Column(String(64), ForeignKey('users.user_id'), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    contacted_at = Column(DateTime, nullable=True)
    
    extra_data = Column(JSON, default={})
    
    __table_args__ = (
        Index('idx_leads_score_status', 'lead_score', 'status'),
        Index('idx_leads_company', 'company_name'),
    )
    
    def to_dict(self) -> Dict:
        return {
            "lead_id": self.lead_id,
            "full_name": self.full_name,
            "email": self.email,
            "company_name": self.company_name,
            "job_title": self.job_title,
            "lead_score": self.lead_score,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


# ═══════════════════════════════════════════════════════════════════
# MODELS - REPORTS & ANALYTICS
# ═══════════════════════════════════════════════════════════════════

class Report(Base):
    """Generated report model"""
    __tablename__ = 'reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.user_id'), nullable=False)
    
    # Report details
    title = Column(String(255), nullable=False)
    report_type = Column(String(50))  # chain_analysis, city_comparison, trend_report
    
    # Parameters used
    parameters = Column(JSON, default={})  # {chains: [], cities: [], date_range: {}}
    
    # Output
    file_url = Column(String(500))
    file_size = Column(Integer)
    format = Column(String(20))  # pdf, xlsx, json
    
    # Status
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="reports")
    
    __table_args__ = (
        Index('idx_reports_user_status', 'user_id', 'status'),
    )


class Anomaly(Base):
    """Detected anomaly model"""
    __tablename__ = 'anomalies'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_id = Column(String(64), unique=True, nullable=False, index=True)
    location_id = Column(String(64), ForeignKey('locations.location_id'), nullable=False)
    
    # Anomaly details
    anomaly_type = Column(String(50))  # spike, drop, trend_change, outlier
    severity = Column(String(20))  # low, medium, high, critical
    
    # Metrics
    value = Column(Float)
    expected_value = Column(Float)
    z_score = Column(Float)
    deviation = Column(Float)
    
    # Context
    detected_at = Column(DateTime, server_default=func.now())
    data_date = Column(DateTime)
    context = Column(JSON, default={})
    
    # Resolution
    is_acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String(64), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_anomalies_location_date', 'location_id', 'detected_at'),
        Index('idx_anomalies_severity', 'severity', 'is_acknowledged'),
    )


# ═══════════════════════════════════════════════════════════════════
# MODELS - PAYMENTS
# ═══════════════════════════════════════════════════════════════════

class Subscription(Base):
    """User subscription model"""
    __tablename__ = 'subscriptions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    subscription_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.user_id'), nullable=False)
    stripe_subscription_id = Column(String(255), unique=True, index=True)
    
    tier = Column(SQLEnum(SubscriptionTierEnum), nullable=False)
    status = Column(String(50))  # active, past_due, cancelled, etc.
    
    # Billing
    amount = Column(Integer)  # cents
    currency = Column(String(3), default="eur")
    interval = Column(String(20))  # month, year
    
    # Period
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Payment(Base):
    """Payment transaction model"""
    __tablename__ = 'payments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(String(64), ForeignKey('users.user_id'), nullable=False)
    stripe_payment_id = Column(String(255), unique=True, index=True)
    
    amount = Column(Integer, nullable=False)  # cents
    currency = Column(String(3), default="eur")
    status = Column(SQLEnum(PaymentStatusEnum), default=PaymentStatusEnum.PENDING)
    
    description = Column(String(500))
    invoice_id = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)
    
    extra_data = Column(JSON, default={})


# ═══════════════════════════════════════════════════════════════════
# DATABASE MANAGER
# ═══════════════════════════════════════════════════════════════════

class DatabaseManager:
    """
    Database Manager for ReviewSignal.
    Handles connections, CRUD operations, and queries.
    """
    
    def __init__(self, database_url: str):
        """
        Initialize Database Manager.
        
        Args:
            database_url: PostgreSQL connection string
                         e.g., postgresql://user:pass@host:5432/dbname
        """
        self.engine = create_engine(
            database_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True
        )
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )
        
        logger.info("database_manager_initialized")
    
    def create_tables(self) -> None:
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("database_tables_created")
    
    def drop_tables(self) -> None:
        """Drop all tables (DANGER!)."""
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("database_tables_dropped")
    
    def get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()
    
    # ───────────────────────────────────────────────────────────────
    # GENERIC CRUD
    # ───────────────────────────────────────────────────────────────
    
    def create(self, session: Session, obj: T) -> T:
        """Create a new record."""
        session.add(obj)
        session.commit()
        session.refresh(obj)
        return obj
    
    def get_by_id(self, session: Session, model: Type[T], id: int) -> Optional[T]:
        """Get record by ID."""
        return session.query(model).filter(model.id == id).first()
    
    def update(self, session: Session, obj: T, **kwargs) -> T:
        """Update record fields."""
        for key, value in kwargs.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        session.commit()
        session.refresh(obj)
        return obj
    
    def delete(self, session: Session, obj: T) -> None:
        """Delete a record."""
        session.delete(obj)
        session.commit()
    
    # ───────────────────────────────────────────────────────────────
    # USER QUERIES
    # ───────────────────────────────────────────────────────────────
    
    def get_user_by_email(self, session: Session, email: str) -> Optional[User]:
        """Get user by email."""
        return session.query(User).filter(User.email == email.lower()).first()
    
    def get_user_by_user_id(self, session: Session, user_id: str) -> Optional[User]:
        """Get user by user_id."""
        return session.query(User).filter(User.user_id == user_id).first()
    
    def get_users_by_company(self, session: Session, company: str) -> List[User]:
        """Get all users in a company."""
        return session.query(User).filter(User.company == company).all()
    
    # ───────────────────────────────────────────────────────────────
    # LOCATION QUERIES
    # ───────────────────────────────────────────────────────────────
    
    def get_locations_by_city(
        self,
        session: Session,
        city: str,
        chain_id: str = None
    ) -> List[Location]:
        """Get locations by city, optionally filtered by chain."""
        query = session.query(Location).filter(Location.city == city)
        if chain_id:
            query = query.filter(Location.chain_id == chain_id)
        return query.all()
    
    def get_locations_by_chain(
        self,
        session: Session,
        chain_id: str
    ) -> List[Location]:
        """Get all locations for a chain."""
        return session.query(Location).filter(Location.chain_id == chain_id).all()
    
    def get_top_rated_locations(
        self,
        session: Session,
        city: str = None,
        limit: int = 10
    ) -> List[Location]:
        """Get top rated locations."""
        query = session.query(Location).filter(Location.is_active == True)
        if city:
            query = query.filter(Location.city == city)
        return query.order_by(Location.current_rating.desc()).limit(limit).all()
    
    # ───────────────────────────────────────────────────────────────
    # LEAD QUERIES
    # ───────────────────────────────────────────────────────────────
    
    def get_leads_by_status(
        self,
        session: Session,
        status: LeadStatusEnum,
        limit: int = 100
    ) -> List[Lead]:
        """Get leads by status."""
        return session.query(Lead).filter(
            Lead.status == status
        ).order_by(Lead.lead_score.desc()).limit(limit).all()
    
    def get_high_value_leads(
        self,
        session: Session,
        min_score: int = 70,
        limit: int = 50
    ) -> List[Lead]:
        """Get high-value leads."""
        return session.query(Lead).filter(
            Lead.lead_score >= min_score,
            Lead.status.in_([LeadStatusEnum.NEW, LeadStatusEnum.QUALIFIED])
        ).order_by(Lead.lead_score.desc()).limit(limit).all()
    
    # ───────────────────────────────────────────────────────────────
    # ANALYTICS QUERIES
    # ───────────────────────────────────────────────────────────────
    
    def get_chain_stats(self, session: Session, chain_id: str) -> Dict:
        """Get aggregated stats for a chain."""
        from sqlalchemy import func
        
        result = session.query(
            func.count(Location.id).label('total_locations'),
            func.avg(Location.current_rating).label('avg_rating'),
            func.sum(Location.review_count).label('total_reviews'),
            func.count(Location.id).filter(Location.is_active == True).label('active_locations')
        ).filter(Location.chain_id == chain_id).first()
        
        return {
            "total_locations": result.total_locations or 0,
            "avg_rating": round(result.avg_rating or 0, 2),
            "total_reviews": result.total_reviews or 0,
            "active_locations": result.active_locations or 0
        }
    
    def get_city_stats(self, session: Session, city: str) -> Dict:
        """Get stats for a city."""
        from sqlalchemy import func
        
        result = session.query(
            func.count(Location.id).label('total_locations'),
            func.avg(Location.current_rating).label('avg_rating'),
            func.count(func.distinct(Location.chain_id)).label('unique_chains')
        ).filter(Location.city == city).first()
        
        return {
            "total_locations": result.total_locations or 0,
            "avg_rating": round(result.avg_rating or 0, 2),
            "unique_chains": result.unique_chains or 0
        }


# ═══════════════════════════════════════════════════════════════════
# RAW SQL QUERIES
# ═══════════════════════════════════════════════════════════════════

RAW_QUERIES = {
    "chain_performance_by_city": """
        SELECT 
            c.name as chain_name,
            l.city,
            COUNT(l.id) as locations,
            ROUND(AVG(l.current_rating)::numeric, 2) as avg_rating,
            SUM(l.review_count) as total_reviews
        FROM locations l
        JOIN chains c ON l.chain_id = c.chain_id
        WHERE l.is_active = true
        GROUP BY c.name, l.city
        ORDER BY avg_rating DESC
    """,
    
    "rating_trends": """
        SELECT 
            DATE(date) as date,
            ROUND(AVG(rating)::numeric, 2) as avg_rating,
            SUM(new_reviews) as new_reviews
        FROM rating_history
        WHERE location_id = :location_id
        AND date >= :start_date
        GROUP BY DATE(date)
        ORDER BY date
    """,
    
    "sentiment_analysis": """
        SELECT 
            sentiment_label,
            COUNT(*) as count,
            ROUND(AVG(sentiment_score)::numeric, 3) as avg_score
        FROM reviews
        WHERE location_id = :location_id
        GROUP BY sentiment_label
    """,
    
    "top_chains_by_growth": """
        WITH recent AS (
            SELECT chain_id, AVG(current_rating) as recent_rating
            FROM locations
            WHERE last_scraped >= NOW() - INTERVAL '30 days'
            GROUP BY chain_id
        ),
        previous AS (
            SELECT chain_id, AVG(current_rating) as prev_rating
            FROM locations
            WHERE last_scraped BETWEEN NOW() - INTERVAL '60 days' AND NOW() - INTERVAL '30 days'
            GROUP BY chain_id
        )
        SELECT 
            c.name,
            r.recent_rating,
            p.prev_rating,
            ROUND((r.recent_rating - p.prev_rating)::numeric, 2) as growth
        FROM recent r
        JOIN previous p ON r.chain_id = p.chain_id
        JOIN chains c ON r.chain_id = c.chain_id
        ORDER BY growth DESC
        LIMIT 20
    """
}


# ═══════════════════════════════════════════════════════════════════
# CLI / MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🗄️  DATABASE SCHEMA - ReviewSignal 5.0")
    print("="*60)
    
    print("\n📊 Models defined:")
    models = [
        ("User", "User accounts & authentication"),
        ("UserSession", "Active user sessions"),
        ("APIKey", "API keys for programmatic access"),
        ("Chain", "Restaurant chains"),
        ("Location", "Individual restaurant locations"),
        ("Review", "Customer reviews with sentiment"),
        ("RatingHistory", "Historical rating trends"),
        ("Lead", "LinkedIn leads for sales"),
        ("Report", "Generated analysis reports"),
        ("Anomaly", "Detected anomalies"),
        ("Subscription", "User subscriptions"),
        ("Payment", "Payment transactions")
    ]
    
    for name, desc in models:
        print(f"   • {name:15} - {desc}")
    
    print("\n🔗 Relationships:")
    print("   • User -> Sessions, APIKeys, Reports")
    print("   • Chain -> Locations")
    print("   • Location -> Reviews, RatingHistory")
    
    print("\n📝 Usage example:")
    print("   db = DatabaseManager('postgresql://user:pass@localhost/reviewsignal')")
    print("   db.create_tables()")
    print("   session = db.get_session()")
    print("   user = db.get_user_by_email(session, 'test@example.com')")
    
    print("\n" + "="*60)
    print("✅ Database Schema ready for PostgreSQL!")
    print("="*60)
