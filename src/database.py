"""Database models and setup for the digest system."""
import json
from datetime import datetime
from typing import List, Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Table, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

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
    created_at = Column(DateTime, default=datetime.utcnow)
    
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
    uploaded_at = Column(DateTime, default=datetime.utcnow)
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
    status = Column(String(20), default='draft')  # draft, published
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    member = relationship('Member', back_populates='digests')
    document = relationship('Document', back_populates='digests')


# Database setup
engine = create_engine('sqlite:///digest_system.db', echo=False)
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Initialize the database."""
    Base.metadata.create_all(engine)


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
