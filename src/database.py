"""Database models and setup for the digest system."""
import json
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Table, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship


def utc_now():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)

Base = declarative_base()

# Association table for many-to-many relationship between members and interests
member_interests = Table(
    'member_interests',
    Base.metadata,
    Column('member_id', Integer, ForeignKey('members.id')),
    Column('interest_id', Integer, ForeignKey('interests.id'))
)


class Member(Base):
    """Member/user model."""
    __tablename__ = 'members'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    
    # Relationships
    interests = relationship('Interest', secondary=member_interests, back_populates='members')
    digests = relationship('Digest', back_populates='member')


class Interest(Base):
    """Interest tag model."""
    __tablename__ = 'interests'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Relationships
    members = relationship('Member', secondary=member_interests, back_populates='interests')


class Document(Base):
    """Document/article model."""
    __tablename__ = 'documents'

    id = Column(Integer, primary_key=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(String(50))  # article, forum, document
    uploaded_at = Column(DateTime, default=utc_now)
    extracted_tags = Column(Text)  # JSON array of extracted interest tags
    
    # Relationships
    digests = relationship('Digest', back_populates='document')


class Digest(Base):
    """Generated digest model."""
    __tablename__ = 'digests'

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey('members.id'), nullable=False)
    document_id = Column(Integer, ForeignKey('documents.id'), nullable=False)
    summary = Column(Text, nullable=False)
    relevance_score = Column(Integer)  # How well it matches member interests
    status = Column(String(20), default='draft')  # draft, pending_review, approved, rejected, published
    created_at = Column(DateTime, default=utc_now)
    reviewed_at = Column(DateTime, nullable=True)  # When admin reviewed
    reviewed_by = Column(String(200), nullable=True)  # Admin who reviewed
    rejection_reason = Column(Text, nullable=True)  # Reason if rejected

    # Relationships
    member = relationship('Member', back_populates='digests')
    document = relationship('Document', back_populates='digests')
    email_queue = relationship('EmailQueue', back_populates='digest', uselist=False)


class EmailQueue(Base):
    """Email queue for digest delivery."""
    __tablename__ = 'email_queue'

    id = Column(Integer, primary_key=True)
    digest_id = Column(Integer, ForeignKey('digests.id'), nullable=False)
    member_id = Column(Integer, ForeignKey('members.id'), nullable=False)
    recipient_email = Column(String(200), nullable=False)
    subject = Column(String(500), nullable=False)
    html_body = Column(Text, nullable=False)
    status = Column(String(20), default='pending')  # pending, sent, failed, retry
    priority = Column(Integer, default=5)  # 1-10, lower = higher priority
    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    error_message = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, default=utc_now)
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    digest = relationship('Digest', back_populates='email_queue')
    member = relationship('Member')


class SchedulerConfig(Base):
    """Configuration for scheduled digest generation."""
    __tablename__ = 'scheduler_config'

    id = Column(Integer, primary_key=True)
    enabled = Column(Integer, default=0)  # 0 = disabled, 1 = enabled (SQLite doesn't have boolean)
    schedule_time = Column(String(5), default='09:00')  # HH:MM format (24-hour)
    schedule_days = Column(String(50), default='1,2,3,4,5')  # Comma-separated: 0=Mon, 6=Sun
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    wordpress_url = Column(String(500), nullable=True)  # WordPress site to fetch from
    posts_per_run = Column(Integer, default=5)
    send_immediately = Column(Integer, default=0)  # Send emails immediately after generation
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


# Database setup
# Enable better concurrent access handling for SQLite
engine = create_engine(
    'sqlite:///digest_system.db',
    echo=False,
    connect_args={
        'check_same_thread': False,
        'timeout': 30  # 30 second timeout for lock
    },
    pool_pre_ping=True  # Verify connections before using
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _migrate_digest_table():
    """Add new columns to digests table for Task 4 (admin review)."""
    import sqlite3

    try:
        conn = sqlite3.connect('digest_system.db')
        cursor = conn.cursor()

        # Check if columns exist
        cursor.execute("PRAGMA table_info(digests)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add new columns if they don't exist
        if 'reviewed_at' not in columns:
            cursor.execute("ALTER TABLE digests ADD COLUMN reviewed_at DATETIME")
            print("✅ Added 'reviewed_at' column to digests table")

        if 'reviewed_by' not in columns:
            cursor.execute("ALTER TABLE digests ADD COLUMN reviewed_by VARCHAR(200)")
            print("✅ Added 'reviewed_by' column to digests table")

        if 'rejection_reason' not in columns:
            cursor.execute("ALTER TABLE digests ADD COLUMN rejection_reason TEXT")
            print("✅ Added 'rejection_reason' column to digests table")

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"⚠️ Migration warning: {e}")


def init_db():
    """Initialize the database."""
    Base.metadata.create_all(engine)

    # Migration: Add new columns to existing digests table if they don't exist
    _migrate_digest_table()


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        return db
    finally:
        pass


def seed_default_interests(db):
    """Seed some default interest tags."""
    default_interests = [
        {"name": "Technology", "description": "Software, hardware, and tech innovations"},
        {"name": "AI/ML", "description": "Artificial Intelligence and Machine Learning"},
        {"name": "Health", "description": "Healthcare, wellness, and medical topics"},
        {"name": "Business", "description": "Business strategy, entrepreneurship, and finance"},
        {"name": "Science", "description": "Scientific research and discoveries"},
        {"name": "Politics", "description": "Political news and analysis"},
        {"name": "Sports", "description": "Sports news and updates"},
        {"name": "Entertainment", "description": "Movies, music, and entertainment"},
        {"name": "Education", "description": "Learning, teaching, and educational content"},
        {"name": "Environment", "description": "Climate, sustainability, and environmental issues"},
    ]

    for interest_data in default_interests:
        existing = db.query(Interest).filter_by(name=interest_data["name"]).first()
        if not existing:
            interest = Interest(**interest_data)
            db.add(interest)

    db.commit()