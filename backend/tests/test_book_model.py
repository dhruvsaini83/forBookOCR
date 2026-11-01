"""Unit and integration tests for Book model, Page foreign key relationship,
database migration script, and database helper functions.
"""

import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from models import Base, Book, BookStatus, Page, Document, get_engine, get_session
from migrate_add_books import run_migration
import core.database as db


@pytest.fixture
def memory_db_session():
    """Provides an isolated in-memory SQLite database session with all models created."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()


def test_book_model_defaults(memory_db_session):
    """Test creating a Book instance with default values as requested."""
    book = Book(name="Shree Bramhanand Janmala Bhajan Mala")
    memory_db_session.add(book)
    memory_db_session.commit()
    memory_db_session.refresh(book)

    assert isinstance(book.id, uuid.UUID)
    assert book.name == "Shree Bramhanand Janmala Bhajan Mala"
    assert book.description is None
    assert book.language == "hin"
    assert book.total_pages == 400
    assert book.cover_image_url is None
    assert book.status == BookStatus.draft
    assert isinstance(book.created_at, datetime)
    assert isinstance(book.updated_at, datetime)

    # Test dictionary serialization
    b_dict = book.to_dict()
    assert b_dict["name"] == "Shree Bramhanand Janmala Bhajan Mala"
    assert b_dict["language"] == "hin"
    assert b_dict["total_pages"] == 400
    assert b_dict["status"] == "draft"
    assert b_dict["pages_count"] == 0


def test_book_model_custom_attributes(memory_db_session):
    """Test creating a Book instance with custom values across all fields."""
    custom_id = uuid.uuid4()
    book = Book(
        id=custom_id,
        name="Bhaktamar Stotra Heritage Edition",
        description="Classical Sanskrit and Devanagari verse preservation",
        language="san",
        total_pages=108,
        cover_image_url="/storage/covers/bhaktamar.jpg",
        status=BookStatus.in_progress
    )
    memory_db_session.add(book)
    memory_db_session.commit()
    memory_db_session.refresh(book)

    assert book.id == custom_id
    assert book.name == "Bhaktamar Stotra Heritage Edition"
    assert book.description == "Classical Sanskrit and Devanagari verse preservation"
    assert book.language == "san"
    assert book.total_pages == 108
    assert book.cover_image_url == "/storage/covers/bhaktamar.jpg"
    assert book.status == BookStatus.in_progress

    # Test updating status to completed
    book.status = BookStatus.completed
    memory_db_session.commit()
    memory_db_session.refresh(book)
    assert book.status == BookStatus.completed


def test_book_page_relationship(memory_db_session):
    """Test 1-to-many relationship between Book and Page with foreign key book_id."""
    # 1. Create a container Document
    doc = Document(
        id="doc_test_1",
        title="Ramcharitmanas Sunderkand",
        original_filename="sunderkand.pdf",
        file_type="pdf",
        total_pages=2,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat()
    )
    memory_db_session.add(doc)

    # 2. Create Book
    book = Book(name="Ramcharitmanas Complete Volume")
    memory_db_session.add(book)
    memory_db_session.flush()

    # 3. Create Pages linked to Document and Book
    page1 = Page(
        id="doc_test_1_p1",
        document_id=doc.id,
        page_number=1,
        book_id=book.id,
        original_image_path="/storage/uploads/page_1.png",
        verified_text="मंगल भवन अमंगल हारी"
    )
    page2 = Page(
        id="doc_test_1_p2",
        document_id=doc.id,
        page_number=2,
        book=book,  # Using relationship directly
        original_image_path="/storage/uploads/page_2.png",
        verified_text="द्रवहु सुदसरथ अजिर बिहारी"
    )
    memory_db_session.add_all([page1, page2])
    memory_db_session.commit()

    # 4. Verify book.pages association
    memory_db_session.refresh(book)
    assert len(book.pages) == 2
    assert {p.page_number for p in book.pages} == {1, 2}
    assert book.pages[0].book_id == book.id
    assert book.to_dict()["pages_count"] == 2


def test_migration_script_on_temp_database(tmp_path):
    """Test running migrate_add_books on a fresh and simulated existing SQLite DB."""
    test_db = tmp_path / "test_migration.db"

    # Step 1: Run on uninitialized DB
    result1 = run_migration(test_db)
    assert result1["status"] == "success"
    assert result1["books_table_created"] is True
    assert "name" in result1["books_columns"]
    assert "status" in result1["books_columns"]

    # Step 2: Idempotent run (should not fail)
    result2 = run_migration(test_db)
    assert result2["status"] == "success"
    assert result2["books_table_created"] is True


def test_database_crud_helpers(tmp_path):
    """Test SQLite helper functions for Book in core.database."""
    # Test save_book
    book = db.save_book(
        name="Shree Bramhanand Janmala Bhajan Mala",
        description="Rare litho printed devotional bhajans",
        language="hin",
        total_pages=400,
        status="draft"
    )
    assert book is not None
    book_id = book["id"]
    assert book["name"] == "Shree Bramhanand Janmala Bhajan Mala"
    assert book["total_pages"] == 400
    assert book["status"] == "draft"

    # Test get_book_by_id
    fetched = db.get_book_by_id(book_id)
    assert fetched is not None
    assert fetched["id"] == book_id
    assert fetched["language"] == "hin"

    # Test update_book
    updated = db.update_book(book_id, status="in_progress", total_pages=420)
    assert updated["status"] == "in_progress"
    assert updated["total_pages"] == 420

    # Test list_books
    books_list = db.list_books(search="Bramhanand")
    assert len(books_list) >= 1
    assert any(b["id"] == book_id for b in books_list)

    # Test delete_book
    deleted = db.delete_book(book_id)
    assert deleted is True
    assert db.get_book_by_id(book_id) is None
