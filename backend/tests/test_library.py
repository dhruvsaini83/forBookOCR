import sys
import uuid
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
import core.database as db
from library import (
    devanagari_to_int,
    parse_combined_text_to_bhajans,
    get_book_bhajans,
    search_book_bhajans,
    init_library_tables
)
from main import app


@pytest.fixture(autouse=True)
def setup_db():
    db.init_db()
    init_library_tables()


def test_devanagari_numeral_conversion():
    assert devanagari_to_int("०") == 0
    assert devanagari_to_int("१२३") == 123
    assert devanagari_to_int("५०८") == 508
    assert devanagari_to_int("42") == 42
    assert devanagari_to_int("भजन १०") == 10
    assert devanagari_to_int("") is None
    assert devanagari_to_int(None) is None


def test_no_auto_naming_rule_enforcement():
    """STRICT RULE: When no title is explicitly authored, title must be 'unknown'.
    Never invent, assume, or hallucinate a title.
    """
    raw_text = """Page 1
भजन क्रमांक 1
जय गणेश जय गणेश देवा
माता जाकी पार्वती पिता महादेवा
एक दन्त दयावन्त चार भुजाधारी
"""
    bhajans = parse_combined_text_to_bhajans(raw_text)
    assert len(bhajans) == 1
    b = bhajans[0]
    assert b["bhajan_number"] == 1
    assert b["title"] == "unknown"  # Strict No-Auto-Naming
    assert b["original_page_number"] == 1
    assert "जय गणेश" in b["starting_lines"]


def test_explicit_title_detection():
    """Explicit titles (bracketed, bold, or prefix) should be detected accurately."""
    raw_text = """Page 1
भजन क्रमांक 1 - श्री गणेश वन्दना
जय गणेश देवा
-------------------------
Page 2
भजन क्रमांक 2
॥ गुरु महिमा ॥
गुरु बिन ज्ञान न उपजै
-------------------------
Page 3
भजन क्रमांक 3
**राम भजन**
रघुपति राघव राजा राम
-------------------------
Page 4
भजन क्रमांक 4
शीर्षक: शिव तांडव स्तोत्र
जटाटवीगलज्जलप्रवाहपावितस्थले
"""
    bhajans = parse_combined_text_to_bhajans(raw_text)
    assert len(bhajans) == 4

    assert bhajans[0]["bhajan_number"] == 1
    assert bhajans[0]["title"] == "श्री गणेश वन्दना"

    assert bhajans[1]["bhajan_number"] == 2
    assert bhajans[1]["title"] == "गुरु महिमा"

    assert bhajans[2]["bhajan_number"] == 3
    assert bhajans[2]["title"] == "राम भजन"

    assert bhajans[3]["bhajan_number"] == 4
    assert bhajans[3]["title"] == "शिव तांडव स्तोत्र"


def test_fts5_and_filter_search():
    book_id = f"test-book-lib-{uuid.uuid4().hex[:8]}"
    db.save_book(
        name="भजन रत्नावली",
        description="प्राचीन हस्तलिखित भजन संग्रह",
        language="hin",
        total_pages=10,
        book_id=book_id
    )

    combined_text = """Page 1
भजन क्रमांक 1 - श्री गणेश वन्दना
जय गणेश जय गणेश देवा
माता जाकी पार्वती पिता महादेवा
-------------------------
Page 2
भजन क्रमांक 2
॥ कृष्ण भजन ॥
बंसी बजैया नन्द लाला
माखन चोर यशोदा नन्दन
-------------------------
Page 3
भजन क्रमांक 3
गोविन्द जय जय गोपाल जय जय
राधा रमण हरि गोविन्द जय जय
"""
    db.save_book_builder(book_id, combined_text, [1, 2, 3], ["p1", "p2", "p3"])

    # Test all bhajans fetch
    all_bhajans = get_book_bhajans(book_id)
    assert len(all_bhajans) == 3
    assert all_bhajans[0]["title"] == "श्री गणेश वन्दना"
    assert all_bhajans[1]["title"] == "कृष्ण भजन"
    assert all_bhajans[2]["title"] == "unknown"  # No auto-naming on Bhajan 3!

    # Search filter: title
    title_matches = search_book_bhajans(book_id, "गणेश", filter_type="title")
    assert len(title_matches) >= 1
    assert title_matches[0]["bhajan_number"] == 1

    # Search filter: number
    num_matches = search_book_bhajans(book_id, "2", filter_type="number")
    assert len(num_matches) == 1
    assert num_matches[0]["bhajan_number"] == 2

    # Search filter: Devanagari number '३'
    num_dev_matches = search_book_bhajans(book_id, "३", filter_type="number")
    assert len(num_dev_matches) == 1
    assert num_dev_matches[0]["bhajan_number"] == 3

    # Search filter: content
    content_matches = search_book_bhajans(book_id, "माखन चोर", filter_type="content")
    assert len(content_matches) >= 1
    assert content_matches[0]["bhajan_number"] == 2

    # Search filter: starting_lines
    start_matches = search_book_bhajans(book_id, "गोविन्द", filter_type="starting_lines")
    assert len(start_matches) >= 1
    assert start_matches[0]["bhajan_number"] == 3


def test_api_bhajans_and_search_endpoints():
    client = TestClient(app)
    book_id = f"test-api-lib-{uuid.uuid4().hex[:8]}"
    db.save_book(
        name="सुन्दरकाण्ड पाण्डुलिपि",
        description="प्राचीन ग्रन्थ",
        language="hin",
        total_pages=5,
        book_id=book_id
    )

    combined_text = """Page 1
भजन क्रमांक 1 - हनुमान चालीसा
जय हनुमान ज्ञान गुन सागर
जय कपीस तिहुं लोक उजागर
-------------------------
Page 2
भजन क्रमांक 2
॥ बजरंग बाण ॥
निश्चय प्रेम प्रतीति ते
विनय करैं सनमान
"""
    db.save_book_builder(book_id, combined_text, [1, 2], ["p1", "p2"])

    # GET /api/books/{book_id}/bhajans
    res = client.get(f"/api/books/{book_id}/bhajans")
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["total"] == 2
    assert len(data["bhajans"]) == 2
    assert data["bhajans"][0]["bhajan_number"] == 1
    assert data["bhajans"][0]["title"] == "हनुमान चालीसा"
    assert data["bhajans"][0]["original_page_number"] == 1

    # GET /api/books/{book_id}/search?q=हनुमान&filter=all
    res_search = client.get(f"/api/books/{book_id}/search?q=हनुमान&filter=all")
    assert res_search.status_code == 200
    search_data = res_search.json()
    assert search_data["success"] is True
    assert search_data["count"] >= 1
    assert search_data["bhajans"][0]["bhajan_number"] == 1

    # Non-existent book 404 test
    res_404 = client.get(f"/api/books/non-existent-id-999/bhajans")
    assert res_404.status_code == 404
