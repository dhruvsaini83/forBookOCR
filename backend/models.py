"""SQLAlchemy models for VaniScript Heritage OCR & Book Preservation Platform.

Defines the Book model, Page model with book foreign key relationship,
Document model, and CorrectionLog model for SQLite.
"""

import uuid
from datetime import datetime, timezone
import enum
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    TypeDecorator,
    create_engine,
    func
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    sessionmaker,
    Session
)

from core.config import DB_PATH

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type for SQLite.

    Stores as String(36) in SQLite database, converts to/from Python uuid.UUID object.
    Accepts both uuid.UUID instances and string UUIDs safely.
    """
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class BookStatus(str, enum.Enum):
    """Lifecycle status for a Book manuscript."""
    draft = "draft"
    in_progress = "in_progress"
    completed = "completed"


class Book(Base):
    """SQLAlchemy model representing a multi-page classical Book / Grantha."""
    __tablename__ = "books"

    # UUID Primary Key
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    
    # Book title / name (e.g. "Shree Bramhanand Janmala Bhajan Mala")
    name = Column(String(255), nullable=False, index=True)
    
    # Detailed manuscript description
    description = Column(Text, nullable=True)
    
    # Language code, default 'hin' (Hindi)
    language = Column(String(20), nullable=False, default="hin", server_default="hin")
    
    # Total planned or scanned pages, default 400
    total_pages = Column(Integer, nullable=False, default=400, server_default="400")
    
    # Optional cover image relative or public URL
    cover_image_url = Column(Text, nullable=True)
    
    # Status enum: 'draft', 'in_progress', 'completed'
    status = Column(
        SQLEnum(
            BookStatus,
            native_enum=False,
            values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        default=BookStatus.draft,
        server_default=BookStatus.draft.value,
        index=True
    )
    
    # Audit timestamps
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # 1-to-many relationship with Page
    pages = relationship(
        "Page",
        back_populates="book",
        cascade="all, delete-orphan"
    )
    builder_collection = relationship(
        "BookBuilderCollection",
        back_populates="book",
        uselist=False,
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Book(id='{self.id}', name='{self.name}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Converts model instance to JSON-serializable dictionary."""
        return {
            "id": str(self.id) if self.id else None,
            "name": self.name,
            "description": self.description,
            "language": self.language,
            "total_pages": self.total_pages,
            "cover_image_url": self.cover_image_url,
            "status": self.status.value if isinstance(self.status, BookStatus) else str(self.status),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "pages_count": len(self.pages) if self.pages else 0
        }




class BookBuilderCollection(Base):
    """SQLAlchemy model for compiling verified pages into a cohesive manuscript publication.
    Maintains combined text, ordered page sequence, and included page IDs.
    """
    __tablename__ = "book_builder_collections"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    book_id = Column(
        GUID(),
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    combined_text = Column(Text, default="")
    page_order = Column(Text, default="[]")  # JSON list of original page_number sequence e.g. [1, 2, 3]
    included_pages = Column(Text, default="[]")  # JSON list of page IDs e.g. ["doc_p1", "doc_p2"]
    separator = Column(
        String(255),
        nullable=False,
        default="\n\n-------------------------\n\n",
        server_default="\n\n-------------------------\n\n"
    )
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    book = relationship("Book", back_populates="builder_collection")

    def __repr__(self) -> str:
        return f"<BookBuilderCollection(id='{self.id}', book_id='{self.book_id}')>"

    def to_dict(self) -> Dict[str, Any]:
        import json
        return {
            "id": str(self.id) if self.id else None,
            "book_id": str(self.book_id) if self.book_id else None,
            "combined_text": self.combined_text or "",
            "page_order": json.loads(self.page_order or "[]"),
            "included_pages": json.loads(self.included_pages or "[]"),
            "separator": self.separator or "\n\n-------------------------\n\n",
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Page(Base):
    """SQLAlchemy model representing an individual scanned page.

    Links to Book via book_id foreign key, and to Document via document_id.
    """
    __tablename__ = "pages"

    id = Column(String(100), primary_key=True)
    document_id = Column(
        String(100),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    page_number = Column(Integer, nullable=False)
    upload_order = Column(Integer, nullable=False, default=1, server_default="1")
    
    # Foreign key referencing Book(id)
    book_id = Column(
        GUID(),
        ForeignKey("books.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Image paths & metrics
    original_image_path = Column(Text, nullable=False)
    preprocessed_image_path = Column(Text, nullable=True)
    quality_metrics_json = Column(Text, default="{}")

    # Text versions (Preservation hierarchy)
    raw_ocr_text = Column(Text, default="")
    original_ocr_text = Column(Text, default="")
    verified_text = Column(Text, default="")
    reviewed_text = Column(Text, default="")
    confirmed_text = Column(Text, default="")

    # OCR tokens and stage verification reports
    word_tokens_json = Column(Text, default="[]")
    stage_metrics_json = Column(Text, default="{}")

    # Status, errors, retries
    status = Column(String(50), nullable=False, default="pending")
    error_code = Column(String(50), default="")
    error_message = Column(Text, default="")
    retry_count = Column(Integer, nullable=False, default=0)

    # Timestamps & provenance
    created_at = Column(String(50), default="")
    updated_at = Column(String(50), default="")
    processed_at = Column(String(50), default="")
    provenance_json = Column(Text, default="{}")

    # Derivative & compression metadata
    adjusted_image_path = Column(Text, default="")
    adjustment_metadata_json = Column(Text, default="{}")
    original_sha256 = Column(Text, default="")
    phash = Column(String(64), default="")
    optimized_image_path = Column(Text, default="")
    compression_metadata_json = Column(Text, default="{}")

    # Multi-engine OCR comparison data
    ocr_engine = Column(String(50), default="tesseract")
    easyocr_text = Column(Text, default="")
    easyocr_tokens_json = Column(Text, default="[]")
    easyocr_metrics_json = Column(Text, default="{}")
    paddleocr_text = Column(Text, default="")
    paddleocr_tokens_json = Column(Text, default="[]")
    paddleocr_metrics_json = Column(Text, default="{}")
    comparison_data_json = Column(Text, default="{}")

    # Relationships
    book = relationship("Book", back_populates="pages")
    document = relationship("Document", back_populates="pages")

    def __repr__(self) -> str:
        return f"<Page(id='{self.id}', doc_id='{self.document_id}', p_num={self.page_number}, upload_order={self.upload_order}, book_id='{self.book_id}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Converts Page model instance to dictionary."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "upload_order": self.upload_order,
            "book_id": str(self.book_id) if self.book_id else None,
            "original_image_path": self.original_image_path,
            "preprocessed_image_path": self.preprocessed_image_path,
            "raw_ocr_text": self.raw_ocr_text,
            "verified_text": self.verified_text,
            "reviewed_text": self.reviewed_text,
            "confirmed_text": self.confirmed_text,
            "status": self.status,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "phash": self.phash,
            "ocr_engine": self.ocr_engine,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


class Document(Base):
    """SQLAlchemy model representing an ingested document container."""
    __tablename__ = "documents"

    id = Column(String(100), primary_key=True)
    title = Column(Text, nullable=False)
    original_filename = Column(Text, nullable=False)
    file_type = Column(String(50), nullable=False)
    total_pages = Column(Integer, nullable=False, default=1)
    processed_pages = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="pending")
    verification_status = Column(String(50), nullable=False, default="Needs Review")
    collection_name = Column(String(100), default="सामान्य (General)")
    metadata_json = Column(Text, default="{}")
    provenance_json = Column(Text, default="{}")
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50), nullable=False)

    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Document(id='{self.id}', title='{self.title}')>"


class CorrectionLog(Base):
    """SQLAlchemy model for immutable append-only correction logs."""
    __tablename__ = "correction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        String(100),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    page_number = Column(Integer, nullable=False)
    word_index = Column(Integer, nullable=False)
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    timestamp = Column(String(50), nullable=False)

    def __repr__(self) -> str:
        return f"<CorrectionLog(id={self.id}, doc_id='{self.document_id}', word_index={self.word_index})>"


def get_engine(db_path=None):
    """Creates a SQLAlchemy engine configured for SQLite with WAL mode and foreign key enforcement."""
    target_path = str(db_path or DB_PATH)
    engine = create_engine(
        f"sqlite:///{target_path}",
        connect_args={"timeout": 30.0, "check_same_thread": False},
        echo=False
    )
    return engine


def get_session(engine=None) -> Session:
    """Creates and returns a new SQLAlchemy Session."""
    eng = engine or get_engine()
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return session_factory()
