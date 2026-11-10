from __future__ import annotations

import io
import re
import uuid

import pytest
from PIL import Image

from app import Hostel, Media, UPLOAD_DIR, app, db


@pytest.fixture()
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def csrf(client) -> str:
    response = client.get("/")
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', response.get_data(as_text=True))
    assert match
    return match.group(1)


def png_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), (40, 120, 200))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_college_search_filtering_and_map_assets(client):
    response = client.get("/")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "HostelFinder" in page
    assert "leaflet@1.9.4" in page
    assert "/static/js/app.js" in page
    assert "use-location" in page

    colleges = client.get("/api/colleges?q=JNTUH").get_json()["colleges"]
    assert colleges and colleges[0]["short_name"] == "JNTUH"
    nearby = client.get("/api/colleges/nearby?latitude=17.4454&longitude=78.3489&radius=5&limit=5")
    nearby_payload = nearby.get_json()
    assert nearby.status_code == 200
    assert nearby_payload["colleges"][0]["short_name"] == "IIIT Hyderabad"
    assert nearby_payload["colleges"][0]["distance_km"] == 0.0
    assert client.get("/api/colleges/nearby?latitude=not-a-coordinate&longitude=78.3").status_code == 400
    results = client.get(f"/api/hostels?college_id={colleges[0]['id']}&radius=5&sort=nearest")
    payload = results.get_json()
    assert results.status_code == 200
    assert payload["count"] >= 5
    distances = [hostel["distance_km"] for hostel in payload["hostels"]]
    assert distances == sorted(distances)
    assert all("walking_minutes" in hostel for hostel in payload["hostels"])


def test_registration_review_edit_helpful_delete_and_listing_upload(client):
    token = csrf(client)
    email = f"student-{uuid.uuid4().hex[:10]}@example.com"
    registered = client.post(
        "/register",
        data={"csrf_token": token, "name": "Test Student", "email": email, "password": "Student123!", "confirm_password": "Student123!"},
        follow_redirects=False,
    )
    assert registered.status_code == 302

    token = csrf(client)
    hostel_id = client.get("/api/hostels?college_id=1&radius=5").get_json()["hostels"][0]["id"]
    invalid_upload = client.post(
        f"/api/hostels/{hostel_id}/reviews",
        data={
            "csrf_token": token,
            "overall_rating": "5",
            "cleanliness": "5",
            "food": "4",
            "safety": "5",
            "value_for_money": "4",
            "wifi": "4",
            "body": "This request should reject the invalid image payload.",
            "media": (io.BytesIO(b"not an image"), "not-really.png"),
        },
        content_type="multipart/form-data",
    )
    assert invalid_upload.status_code == 400
    review_data = {
        "csrf_token": token,
        "overall_rating": "5",
        "cleanliness": "5",
        "food": "4",
        "safety": "5",
        "value_for_money": "4",
        "wifi": "4",
        "body": "A useful test review with enough detail for validation.",
        "media": (io.BytesIO(png_bytes()), "room.png"),
    }
    created = client.post(f"/api/hostels/{hostel_id}/reviews", data=review_data, content_type="multipart/form-data")
    assert created.status_code == 201
    review_id = created.get_json()["review"]["id"]
    duplicate = client.post(
        f"/api/hostels/{hostel_id}/reviews",
        data={**review_data, "media": []},
        content_type="multipart/form-data",
    )
    assert duplicate.status_code == 409

    edited = client.put(
        f"/api/reviews/{review_id}",
        data={
            "overall_rating": "4",
            "cleanliness": "4",
            "food": "4",
            "safety": "5",
            "value_for_money": "4",
            "wifi": "5",
            "body": "Edited test review with updated information for students.",
        },
        headers={"X-CSRFToken": token},
    )
    assert edited.status_code == 200
    helpful = client.post(f"/api/reviews/{review_id}/helpful", headers={"X-CSRFToken": token})
    assert helpful.status_code == 200
    deleted = client.delete(f"/api/reviews/{review_id}", headers={"X-CSRFToken": token})
    assert deleted.status_code == 200

    listing_data = {
        "csrf_token": token,
        "name": "Test Pending Homes",
        "description": "A sufficiently detailed test listing for the approval workflow.",
        "address": "Test Street, Hyderabad",
        "area": "Kondapur",
        "latitude": "17.4600",
        "longitude": "78.3700",
        "hostel_type": "co-living",
        "price_min": "8000",
        "price_max": "10000",
        "food_included": "true",
        "ac_available": "true",
        "sharing_type": "double",
        "phone": "+91 98765 43210",
        "email": "listing@example.com",
        "amenities": "WiFi, laundry",
        "media": (io.BytesIO(png_bytes()), "front.png"),
    }
    listing = client.post("/api/hostels", data=listing_data, content_type="multipart/form-data")
    assert listing.status_code == 201
    created_id = listing.get_json()["hostel_id"]
    with app.app_context():
        created_hostel = db.session.get(Hostel, created_id)
        assert created_hostel.status == "pending"
        assert Media.query.filter_by(hostel_id=created_id).count() == 1
        for media in list(created_hostel.media):
            if media.filename:
                (UPLOAD_DIR / media.filename).unlink(missing_ok=True)
        db.session.delete(created_hostel)
        db.session.commit()


def test_admin_page_and_protected_api(client):
    token = csrf(client)
    login = client.post("/login", data={"csrf_token": token, "email": "admin@hostelfinder.local", "password": "Admin123!"})
    assert login.status_code == 302
    assert client.get("/admin").status_code == 200
    response = client.post("/api/admin/hostels/999999/status", json={"status": "approved"}, headers={"X-CSRFToken": csrf(client)})
    assert response.status_code == 404
