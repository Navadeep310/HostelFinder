"""HostelFinder: a small, production-minded Flask app for student housing.

The app intentionally keeps the stack simple: Flask routes serve HTML, the
JSON endpoints power the interactive map, and SQLite stores all application
data.  Sample records are marked throughout the database and UI so they are
never confused with student-submitted information.
"""

from __future__ import annotations

import json
import math
import os
import re
import secrets
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from PIL import Image, UnidentifiedImageError
from sqlalchemy import UniqueConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
UPLOAD_DIR = BASE_DIR / "uploads"
THUMB_DIR = UPLOAD_DIR / "thumbnails"
DATABASE_PATH = INSTANCE_DIR / "hostelfinder.db"

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
# A listing can contain up to eight individually validated files. The per-file
# limits below still apply; this only prevents Flask from rejecting a valid
# multi-file listing before the application can validate each item.
MAX_CONTENT_BYTES = 8 * MAX_VIDEO_BYTES + 8 * MAX_IMAGE_BYTES
HOSTEL_TYPES = {"boys", "girls", "co-living"}
SHARING_TYPES = {"single", "double", "triple"}
HOSTEL_STATUSES = {"pending", "approved", "rejected"}

db = SQLAlchemy()


def utc_now() -> datetime:
    """Return a naive UTC timestamp suitable for SQLite DateTime columns."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    reviews = db.relationship("Review", back_populates="author", cascade="all, delete-orphan")
    hostels = db.relationship("Hostel", back_populates="creator")


class College(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(180), nullable=False, unique=True)
    short_name = db.Column(db.String(80), nullable=False)
    area = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    hostels = db.relationship("Hostel", back_populates="college")


class Hostel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)
    address = db.Column(db.String(300), nullable=False)
    area = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    hostel_type = db.Column(db.String(20), nullable=False)
    price_min = db.Column(db.Integer, nullable=False)
    price_max = db.Column(db.Integer, nullable=False)
    food_included = db.Column(db.Boolean, default=False, nullable=False)
    ac_available = db.Column(db.Boolean, default=False, nullable=False)
    sharing_type = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    amenities_json = db.Column(db.Text, nullable=False, default="[]")
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    college_id = db.Column(db.Integer, db.ForeignKey("college.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    creator = db.relationship("User", back_populates="hostels")
    college = db.relationship("College", back_populates="hostels")
    media = db.relationship("Media", back_populates="hostel", cascade="all, delete-orphan")
    reviews = db.relationship("Review", back_populates="hostel", cascade="all, delete-orphan")


class Media(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey("hostel.id"), nullable=False)
    review_id = db.Column(db.Integer, db.ForeignKey("review.id"), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    thumbnail_filename = db.Column(db.String(255), nullable=True)
    original_name = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)  # image or video
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    is_removed = db.Column(db.Boolean, default=False, nullable=False)
    uploaded_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    hostel = db.relationship("Hostel", back_populates="media")
    review = db.relationship("Review", back_populates="media")


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostel_id = db.Column(db.Integer, db.ForeignKey("hostel.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    overall_rating = db.Column(db.Integer, nullable=False)
    cleanliness = db.Column(db.Integer, nullable=False)
    food = db.Column(db.Integer, nullable=False)
    safety = db.Column(db.Integer, nullable=False)
    value_for_money = db.Column(db.Integer, nullable=False)
    wifi = db.Column(db.Integer, nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="visible", nullable=False, index=True)
    is_sample = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    hostel = db.relationship("Hostel", back_populates="reviews")
    author = db.relationship("User", back_populates="reviews")
    media = db.relationship("Media", back_populates="review", cascade="all, delete-orphan")
    helpful_votes = db.relationship("HelpfulVote", back_populates="review", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("hostel_id", "user_id", name="one_review_per_user_hostel"),)


class HelpfulVote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey("review.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    review = db.relationship("Review", back_populates="helpful_votes")
    __table_args__ = (UniqueConstraint("review_id", "user_id", name="one_helpful_vote_per_user"),)


app = Flask(__name__, instance_path=str(INSTANCE_DIR), instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY=os.environ.get("HOSTELFINDER_SECRET_KEY", "dev-only-change-this-secret"),
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", f"sqlite:///{DATABASE_PATH}"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    MAX_CONTENT_LENGTH=MAX_CONTENT_BYTES,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
db.init_app(app)


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


@app.context_processor
def inject_template_helpers() -> dict[str, Any]:
    return {
        "csrf_token": get_csrf_token,
        "current_user": g.get("user"),
        "current_user_data": (
            {"id": g.user.id, "name": g.user.name, "email": g.user.email, "is_admin": g.user.is_admin}
            if g.get("user")
            else None
        ),
    }


@app.template_filter("pretty_date")
def pretty_date(value: datetime | None) -> str:
    if not value:
        return ""
    return value.strftime("%b %d, %Y").replace(" 0", " ")


@app.before_request
def load_user_and_protect_forms() -> None:
    user_id = session.get("user_id")
    g.user = db.session.get(User, user_id) if user_id else None

    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        supplied = request.headers.get("X-CSRFToken") or request.form.get("csrf_token")
        expected = session.get("csrf_token", "")
        if not supplied or not secrets.compare_digest(supplied, expected):
            if request.path.startswith("/api/"):
                return jsonify(error="Your session token expired. Refresh the page and try again."), 400
            abort(400, description="Your session token expired. Refresh the page and try again.")


@app.errorhandler(400)
def bad_request(error: Any):
    message = getattr(error, "description", "The request could not be understood.")
    if request.path.startswith("/api/"):
        return jsonify(error=message), 400
    return render_template("error.html", code=400, message=message), 400


@app.errorhandler(404)
def not_found(error: Any):
    if request.path.startswith("/api/"):
        return jsonify(error="That resource was not found."), 404
    return render_template("error.html", code=404, message="We couldn't find that page."), 404


@app.errorhandler(413)
def file_too_large(error: Any):
    message = "That upload is too large. Images are limited to 5 MB and videos to 50 MB."
    if request.path.startswith("/api/"):
        return jsonify(error=message), 413
    return render_template("error.html", code=413, message=message), 413


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.get("user"):
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in to continue.", login_url=url_for("login")), 401
            flash("Please log in to continue.", "info")
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not g.user.is_admin:
            if request.path.startswith("/api/"):
                return jsonify(error="Admin access is required."), 403
            return render_template("error.html", code=403, message="Admin access is required."), 403
        return view(*args, **kwargs)

    return wrapped


def json_or_form_data() -> dict[str, Any]:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict()


def clean_text(value: Any, field: str, minimum: int = 1, maximum: int = 500) -> str:
    text = str(value or "").strip()
    if len(text) < minimum or len(text) > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum} characters.")
    return text


def parse_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}.")
    return number


def parse_float(value: Any, field: str, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number.") from exc
    if not minimum <= number <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}.")
    return number


def parse_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes", "on"}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance in kilometres between two coordinates."""

    earth_radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    return earth_radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def walking_minutes(distance_km: float) -> int:
    return max(1, round(distance_km * 12))


def amenities_for(hostel: Hostel) -> list[str]:
    try:
        value = json.loads(hostel.amenities_json or "[]")
        return [str(item) for item in value] if isinstance(value, list) else []
    except json.JSONDecodeError:
        return [item.strip() for item in hostel.amenities_json.split(",") if item.strip()]


def rating_summary(hostel: Hostel) -> dict[str, Any]:
    reviews = [review for review in hostel.reviews if review.status == "visible"]
    count = len(reviews)
    fields = {"cleanliness": 0.0, "food": 0.0, "safety": 0.0, "value_for_money": 0.0, "wifi": 0.0}
    if count:
        for field in fields:
            fields[field] = round(sum(getattr(review, field) for review in reviews) / count, 1)
        overall = round(sum(review.overall_rating for review in reviews) / count, 1)
    else:
        overall = 0.0
    breakdown = {
        field: {"rating": rating, "percent": round(rating / 5 * 100) if rating else 0}
        for field, rating in fields.items()
    }
    return {"average": overall, "count": count, "breakdown": breakdown}


def media_payload(media: Media) -> dict[str, Any] | None:
    if media.is_removed:
        return None
    return {
        "id": media.id,
        "url": url_for("uploaded_file", filename=media.filename),
        "thumbnail_url": url_for("uploaded_file", filename=f"thumbnails/{media.thumbnail_filename}")
        if media.thumbnail_filename
        else url_for("uploaded_file", filename=media.filename),
        "media_type": media.media_type,
        "original_name": media.original_name,
        "is_sample": media.is_sample,
    }


def review_payload(review: Review) -> dict[str, Any]:
    current_id = g.user.id if g.get("user") else None
    media = [payload for item in review.media if (payload := media_payload(item))]
    return {
        "id": review.id,
        "reviewer": review.author.name if review.author else "Student",
        "date": pretty_date(review.created_at),
        "overall_rating": review.overall_rating,
        "cleanliness": review.cleanliness,
        "food": review.food,
        "safety": review.safety,
        "value_for_money": review.value_for_money,
        "wifi": review.wifi,
        "body": review.body,
        "helpful_count": len(review.helpful_votes),
        "is_sample": review.is_sample,
        "can_edit": current_id == review.user_id,
        "media": media,
    }


def hostel_payload(hostel: Hostel, distance: float | None = None, include_reviews: bool = True) -> dict[str, Any]:
    summary = rating_summary(hostel)
    media = [payload for item in hostel.media if (payload := media_payload(item)) and item.review_id is None]
    payload: dict[str, Any] = {
        "id": hostel.id,
        "name": hostel.name,
        "description": hostel.description,
        "address": hostel.address,
        "area": hostel.area,
        "latitude": hostel.latitude,
        "longitude": hostel.longitude,
        "hostel_type": hostel.hostel_type,
        "price_min": hostel.price_min,
        "price_max": hostel.price_max,
        "food_included": hostel.food_included,
        "ac_available": hostel.ac_available,
        "sharing_type": hostel.sharing_type,
        "phone": hostel.phone,
        "email": hostel.email,
        "amenities": amenities_for(hostel),
        "status": hostel.status,
        "is_sample": hostel.is_sample,
        "rating": summary["average"],
        "review_count": summary["count"],
        "rating_breakdown": summary["breakdown"],
        "media": media,
        "distance_km": round(distance, 2) if distance is not None else None,
        "walking_minutes": walking_minutes(distance) if distance is not None else None,
        "directions_url": (
            "https://www.google.com/maps/dir/?api=1&destination="
            f"{hostel.latitude},{hostel.longitude}"
        ),
        "college": (
            {
                "id": hostel.college.id,
                "name": hostel.college.name,
                "latitude": hostel.college.latitude,
                "longitude": hostel.college.longitude,
            }
            if hostel.college
            else None
        ),
    }
    if include_reviews:
        payload["reviews"] = [
            review_payload(review)
            for review in sorted(hostel.reviews, key=lambda item: item.created_at, reverse=True)
            if review.status == "visible"
        ]
    return payload


def allowed_extension(filename: str) -> tuple[str, str]:
    extension = Path(filename).suffix.lower().lstrip(".")
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return extension, "image"
    if extension in ALLOWED_VIDEO_EXTENSIONS:
        return extension, "video"
    raise ValueError("Only JPG, PNG, WEBP, MP4, and WEBM files are allowed.")


def save_upload(file_storage, hostel_id: int, review_id: int | None = None, is_sample: bool = False) -> Media:
    if not file_storage or not file_storage.filename:
        raise ValueError("Choose a file to upload.")
    original_name = secure_filename(file_storage.filename)[:255]
    extension, media_type = allowed_extension(original_name)
    stream = file_storage.stream
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(0)
    limit = MAX_IMAGE_BYTES if media_type == "image" else MAX_VIDEO_BYTES
    if size <= 0 or size > limit:
        label = "5 MB" if media_type == "image" else "50 MB"
        raise ValueError(f"{original_name} exceeds the {label} limit or is empty.")

    stored_name = f"{uuid4().hex}.{extension}"
    target = UPLOAD_DIR / stored_name
    thumbnail_name = None
    if media_type == "image":
        try:
            image = Image.open(stream)
            image.verify()
            stream.seek(0)
            image = Image.open(stream)
            image.thumbnail((720, 520))
            thumb_image = image.convert("RGB")
            thumbnail_name = f"{uuid4().hex}.jpg"
            thumb_image.save(THUMB_DIR / thumbnail_name, "JPEG", quality=84, optimize=True)
            stream.seek(0)
        except (UnidentifiedImageError, OSError) as exc:
            raise ValueError("That image could not be validated. Try a JPG, PNG, or WEBP file.") from exc
    else:
        # Extension checks alone are too easy to spoof. These lightweight
        # container signatures reject common non-video uploads without
        # requiring ffmpeg or another heavyweight dependency.
        header = stream.read(64)
        stream.seek(0)
        is_mp4 = len(header) >= 12 and header[4:8] == b"ftyp"
        is_webm = header.startswith(b"\x1a\x45\xdf\xa3")
        if (extension == "mp4" and not is_mp4) or (extension == "webm" and not is_webm):
            raise ValueError("That video could not be validated. Upload a real MP4 or WEBM file.")
    file_storage.save(target)
    return Media(
        hostel_id=hostel_id,
        review_id=review_id,
        filename=stored_name,
        thumbnail_filename=thumbnail_name,
        original_name=original_name,
        media_type=media_type,
        is_sample=is_sample,
    )


def remove_media_files(media: Media) -> None:
    for path in [UPLOAD_DIR / media.filename, THUMB_DIR / media.thumbnail_filename if media.thumbnail_filename else None]:
        if path and path.exists():
            path.unlink(missing_ok=True)


def validate_review_data(data: dict[str, Any]) -> dict[str, Any]:
    values = {}
    for field, label in [
        ("overall_rating", "Overall rating"),
        ("cleanliness", "Cleanliness rating"),
        ("food", "Food rating"),
        ("safety", "Safety rating"),
        ("value_for_money", "Value for money rating"),
        ("wifi", "WiFi rating"),
    ]:
        values[field] = parse_int(data.get(field), label, 1, 5)
    values["body"] = clean_text(data.get("body"), "Review", 10, 2_000)
    return values


def validate_hostel_data(data: dict[str, Any]) -> dict[str, Any]:
    hostel_type = str(data.get("hostel_type", "")).lower()
    sharing_type = str(data.get("sharing_type", "")).lower()
    if hostel_type not in HOSTEL_TYPES:
        raise ValueError("Choose boys, girls, or co-living.")
    if sharing_type not in SHARING_TYPES:
        raise ValueError("Choose single, double, or triple sharing.")
    price_min = parse_int(data.get("price_min"), "Minimum price", 500, 200_000)
    price_max = parse_int(data.get("price_max"), "Maximum price", price_min, 250_000)
    return {
        "name": clean_text(data.get("name"), "Hostel name", 3, 160),
        "description": clean_text(data.get("description"), "Description", 20, 3_000),
        "address": clean_text(data.get("address"), "Address", 5, 300),
        "area": clean_text(data.get("area"), "Area", 2, 100),
        "latitude": parse_float(data.get("latitude"), "Latitude", -90, 90),
        "longitude": parse_float(data.get("longitude"), "Longitude", -180, 180),
        "hostel_type": hostel_type,
        "price_min": price_min,
        "price_max": price_max,
        "food_included": bool(parse_bool(data.get("food_included"))),
        "ac_available": bool(parse_bool(data.get("ac_available"))),
        "sharing_type": sharing_type,
        "phone": clean_text(data.get("phone"), "Phone", 7, 30),
        "email": clean_text(data.get("email"), "Email", 5, 255),
        "amenities_json": json.dumps(
            [item.strip() for item in str(data.get("amenities", "")).split(",") if item.strip()][:20]
        ),
    }


# These are campus coordinates, checked against the public campus locations.
# Seeded listings are deliberately illustrative and are labelled everywhere.
COLLEGE_SEEDS = [
    {"name": "Jawaharlal Nehru Technological University Hyderabad", "short_name": "JNTUH", "area": "Kukatpally", "latitude": 17.4933, "longitude": 78.3915},
    {"name": "Osmania University", "short_name": "OU", "area": "Amberpet", "latitude": 17.4126, "longitude": 78.5260},
    {"name": "International Institute of Information Technology Hyderabad", "short_name": "IIIT Hyderabad", "area": "Gachibowli", "latitude": 17.4454, "longitude": 78.3489},
    {"name": "Chaitanya Bharathi Institute of Technology", "short_name": "CBIT", "area": "Gandipet", "latitude": 17.3910, "longitude": 78.3197},
    {"name": "VNR Vignana Jyothi Institute of Engineering and Technology", "short_name": "VNR VJIET", "area": "Bachupally", "latitude": 17.5314, "longitude": 78.3698},
    {"name": "Vasavi College of Engineering", "short_name": "Vasavi", "area": "Mehdipatnam", "latitude": 17.3616, "longitude": 78.5260},
    {"name": "CVR College of Engineering", "short_name": "CVR", "area": "Ibrahimpatnam", "latitude": 17.2449, "longitude": 78.6880},
    {"name": "Mahatma Gandhi Institute of Technology", "short_name": "MGIT", "area": "Gandipet", "latitude": 17.3844, "longitude": 78.4574},
    {"name": "Gokaraju Rangaraju Institute of Engineering and Technology", "short_name": "GRIET", "area": "Bachupally", "latitude": 17.5228, "longitude": 78.3665},
    {"name": "Anurag University", "short_name": "Anurag University", "area": "Ghatkesar", "latitude": 17.4116, "longitude": 78.6550},
    {"name": "Sreenidhi Institute of Science and Technology", "short_name": "Sreenidhi", "area": "Ghatkesar", "latitude": 17.5616, "longitude": 78.6839},
    {"name": "BVRIT Hyderabad College of Engineering for Women", "short_name": "BVRIT Hyderabad", "area": "Bachupally", "latitude": 17.5183, "longitude": 78.3052},
    {"name": "CMR College of Engineering and Technology", "short_name": "CMRCET", "area": "Kandlakoya", "latitude": 17.5672, "longitude": 78.4745},
    {"name": "Malla Reddy Engineering College", "short_name": "MREC", "area": "Maisammaguda", "latitude": 17.5726, "longitude": 78.4840},
    {"name": "St. Martin's Engineering College", "short_name": "SMEC", "area": "Dhulapally", "latitude": 17.5532, "longitude": 78.4412},
    {"name": "University of Hyderabad", "short_name": "UoH", "area": "Gachibowli", "latitude": 17.4576, "longitude": 78.3336},
    {"name": "ICFAI Business School Hyderabad", "short_name": "IBS Hyderabad", "area": "Shankarpally", "latitude": 17.4388, "longitude": 78.3372},
    {"name": "Keshav Memorial Institute of Technology", "short_name": "KMIT", "area": "Narayanguda", "latitude": 17.3972, "longitude": 78.4903},
]


def write_sample_svg(path: Path, title: str, area: str, hue: int) -> None:
    """Create a lightweight local illustration for sample listings.

    We do not present these illustrations as real property photographs. They
    make the seeded demo pleasant to explore while all real uploads still go
    through the image validation pipeline above.
    """

    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_title = re.sub(r"[^A-Za-z0-9 &-]", "", title)[:34]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="760" viewBox="0 0 1200 760">
      <defs><linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop stop-color="hsl({hue},70%,35%)"/><stop offset="1" stop-color="hsl({(hue + 55) % 360},72%,58%)"/></linearGradient></defs>
      <rect width="1200" height="760" fill="url(#bg)"/><circle cx="990" cy="110" r="180" fill="#ffffff" opacity=".12"/><circle cx="180" cy="690" r="260" fill="#ffffff" opacity=".08"/>
      <rect x="170" y="160" width="860" height="440" rx="34" fill="#ffffff" opacity=".94"/><path d="M250 420h700v120H250z" fill="#e9eef5"/><path d="M330 260h540l80 100H250z" fill="#c7d3e2"/><rect x="360" y="375" width="130" height="95" rx="10" fill="#85b8d5"/><rect x="535" y="375" width="130" height="95" rx="10" fill="#85b8d5"/><rect x="710" y="375" width="130" height="95" rx="10" fill="#85b8d5"/><rect x="550" y="480" width="100" height="120" rx="8" fill="#496077"/>
      <text x="600" y="90" text-anchor="middle" font-family="Arial,sans-serif" font-size="30" font-weight="700" fill="#fff">SAMPLE DATA</text><text x="600" y="665" text-anchor="middle" font-family="Arial,sans-serif" font-size="38" font-weight="700" fill="#1a2940">{safe_title}</text><text x="600" y="710" text-anchor="middle" font-family="Arial,sans-serif" font-size="25" fill="#45576e">Illustrative listing • {area}</text>
    </svg>"""
    path.write_text(svg, encoding="utf-8")


def seed_database() -> None:
    """Create a useful demo dataset once, without overwriting user data."""

    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    db.create_all()

    colleges = College.query.order_by(College.id).all()
    if not colleges:
        colleges = [College(**item) for item in COLLEGE_SEEDS]
        db.session.add_all(colleges)
        db.session.flush()

    sample_user = User.query.filter_by(email="sample@hostelfinder.local").first()
    if not sample_user:
        sample_user = User(
            name="HostelFinder Sample",
            email="sample@hostelfinder.local",
            password_hash=generate_password_hash("SampleOnly123!"),
        )
        db.session.add(sample_user)

    admin = User.query.filter_by(email="admin@hostelfinder.local").first()
    if not admin:
        admin = User(
            name="HostelFinder Admin",
            email="admin@hostelfinder.local",
            password_hash=generate_password_hash("Admin123!"),
            is_admin=True,
        )
        db.session.add(admin)

    db.session.flush()
    if Hostel.query.count() == 0:
        hostel_templates = [
            ("CampusNest", "boys", "double", 6500, 8500, True, False),
            ("StudyStay", "girls", "triple", 5800, 7600, True, False),
            ("Metro Homes", "co-living", "single", 9000, 12500, False, True),
            ("Green Door", "co-living", "double", 7200, 9800, True, True),
            ("Scholar's Corner", "boys", "triple", 5200, 7000, True, False),
            ("Urban Nest", "girls", "single", 10500, 14500, False, True),
        ]
        offsets = [(0.008, 0.009), (-0.012, 0.007), (0.015, -0.013), (-0.018, -0.010), (0.005, -0.020), (-0.006, 0.018)]
        for college_index, college in enumerate(colleges):
            for item_index, (prefix, hostel_type, sharing, minimum, maximum, food, ac) in enumerate(hostel_templates):
                lat_offset, lon_offset = offsets[item_index]
                # A small deterministic spread keeps each campus's examples nearby.
                lat = college.latitude + lat_offset + college_index * 0.00012
                lon = college.longitude + lon_offset - college_index * 0.00008
                hostel = Hostel(
                    name=f"{prefix} {college.short_name}",
                    description=(
                        "Sample data only — this illustrative listing demonstrates HostelFinder's search, map, and review experience. "
                        "Confirm availability, pricing, safety arrangements, and house rules directly before booking."
                    ),
                    address=f"{college.area} • Sample listing near {college.short_name}",
                    area=college.area,
                    latitude=lat,
                    longitude=lon,
                    hostel_type=hostel_type,
                    price_min=minimum + college_index * 100,
                    price_max=maximum + college_index * 100,
                    food_included=food,
                    ac_available=ac,
                    sharing_type=sharing,
                    phone="+91 90000 00000",
                    email="sample-listing@hostelfinder.local",
                    amenities_json=json.dumps(["WiFi", "24/7 security", "Laundry", "Power backup"] + (["Food included"] if food else [])),
                    status="approved",
                    is_sample=True,
                    created_by=sample_user.id,
                    college_id=college.id,
                )
                db.session.add(hostel)
        db.session.flush()

        for hostel in Hostel.query.filter_by(is_sample=True).all():
            stored_name = f"sample-hostel-{hostel.id}.svg"
            write_sample_svg(UPLOAD_DIR / stored_name, hostel.name, hostel.area, (hostel.id * 31) % 360)
            db.session.add(
                Media(
                    hostel_id=hostel.id,
                    filename=stored_name,
                    original_name="sample-illustration.svg",
                    media_type="image",
                    is_sample=True,
                )
            )

        # Deliberately repetitive and explicit sample copy: these are layout
        # examples, not fabricated student experiences presented as real.
        for hostel in Hostel.query.filter_by(is_sample=True).all():
            if hostel.id % 3 == 1:
                db.session.add(
                    Review(
                        hostel_id=hostel.id,
                        user_id=sample_user.id,
                        overall_rating=4,
                        cleanliness=4,
                        food=4,
                        safety=5,
                        value_for_money=4,
                        wifi=4,
                        body="Sample data only — this review demonstrates the rating layout. Replace it with a verified student experience.",
                        is_sample=True,
                    )
                )
    db.session.commit()


@app.route("/uploads/<path:filename>")
def uploaded_file(filename: str):
    # send_from_directory prevents path traversal and only serves the local
    # upload directory, including its generated thumbnail subdirectory.
    return send_from_directory(str(UPLOAD_DIR), filename, as_attachment=False)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/hostel/<int:hostel_id>")
def hostel_detail(hostel_id: int):
    hostel = Hostel.query.filter_by(id=hostel_id, status="approved").first_or_404()
    return render_template("hostel_detail.html", hostel=hostel_payload(hostel))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = str(request.form.get("email", "")).strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.email) == email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash("Email or password not recognised.", "error")
            return render_template("auth.html", mode="login"), 401
        session.clear()
        session["user_id"] = user.id
        get_csrf_token()
        flash(f"Welcome back, {user.name.split()[0]}.", "success")
        destination = request.args.get("next") or url_for("index")
        return redirect(destination)
    return render_template("auth.html", mode="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        try:
            name = clean_text(request.form.get("name"), "Name", 2, 80)
            email = clean_text(request.form.get("email"), "Email", 5, 255).lower()
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise ValueError("Enter a valid email address.")
            password = request.form.get("password", "")
            if len(password) < 8 or len(password) > 128:
                raise ValueError("Password must be between 8 and 128 characters.")
            if password != request.form.get("confirm_password", ""):
                raise ValueError("Passwords do not match.")
            if User.query.filter(func.lower(User.email) == email).first():
                raise ValueError("An account with that email already exists.")
            user = User(name=name, email=email, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            get_csrf_token()
            flash("Your account is ready. Welcome to HostelFinder!", "success")
            return redirect(url_for("index"))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return render_template("auth.html", mode="register"), 400
    return render_template("auth.html", mode="register")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.get("/api/colleges")
def api_colleges():
    query = str(request.args.get("q", "")).strip()
    statement = College.query.order_by(College.name)
    if query:
        statement = statement.filter(
            db.or_(College.name.ilike(f"%{query}%"), College.short_name.ilike(f"%{query}%"), College.area.ilike(f"%{query}%"))
        )
    colleges = statement.limit(15).all()
    return jsonify(
        colleges=[
            {
                "id": college.id,
                "name": college.name,
                "short_name": college.short_name,
                "area": college.area,
                "latitude": college.latitude,
                "longitude": college.longitude,
            }
            for college in colleges
        ]
    )


@app.get("/api/colleges/nearby")
def api_nearby_colleges():
    """Return seeded colleges ordered by distance from browser-provided GPS.

    The browser supplies coordinates through the Geolocation API; no Google
    Maps key or server-side location tracking is needed. Coordinates are only
    used for this request and are never stored.
    """

    try:
        latitude = parse_float(request.args.get("latitude", request.args.get("lat")), "Latitude", -90, 90)
        longitude = parse_float(request.args.get("longitude", request.args.get("lng", request.args.get("lon"))), "Longitude", -180, 180)
        radius = parse_float(request.args.get("radius", 50), "Radius", 1, 100)
        limit = parse_int(request.args.get("limit", 8), "Limit", 1, 50)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    nearby = []
    for college in College.query.all():
        distance = haversine_km(latitude, longitude, college.latitude, college.longitude)
        if distance <= radius:
            nearby.append((college, distance))
    nearby.sort(key=lambda item: item[1])

    return jsonify(
        origin={"latitude": latitude, "longitude": longitude},
        radius_km=radius,
        colleges=[
            {
                "id": college.id,
                "name": college.name,
                "short_name": college.short_name,
                "area": college.area,
                "latitude": college.latitude,
                "longitude": college.longitude,
                "distance_km": round(distance, 2),
            }
            for college, distance in nearby[:limit]
        ],
    )


@app.get("/api/hostels")
def api_hostels():
    try:
        college_id = parse_int(request.args.get("college_id"), "College", 1, 10_000_000)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    college = db.session.get(College, college_id)
    if not college:
        return jsonify(error="Choose a college from the suggestions first."), 404
    try:
        radius = float(request.args.get("radius", 5))
        if radius not in {1, 3, 5, 10}:
            raise ValueError
    except ValueError:
        return jsonify(error="Radius must be 1, 3, 5, or 10 km."), 400

    query = Hostel.query.filter_by(status="approved")
    hostel_type = str(request.args.get("type", "")).lower()
    sharing = str(request.args.get("sharing", "")).lower()
    if hostel_type in HOSTEL_TYPES:
        query = query.filter_by(hostel_type=hostel_type)
    if sharing in SHARING_TYPES:
        query = query.filter_by(sharing_type=sharing)
    food = parse_bool(request.args.get("food"))
    ac = parse_bool(request.args.get("ac"))
    if food is not None:
        query = query.filter_by(food_included=food)
    if ac is not None:
        query = query.filter_by(ac_available=ac)

    try:
        min_price = parse_int(request.args.get("min_price"), "Minimum price", 0, 250_000) if request.args.get("min_price") else None
        max_price = parse_int(request.args.get("max_price"), "Maximum price", 0, 250_000) if request.args.get("max_price") else None
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    hostels_with_distance = []
    for hostel in query.all():
        distance = haversine_km(college.latitude, college.longitude, hostel.latitude, hostel.longitude)
        if distance > radius:
            continue
        if min_price is not None and hostel.price_max < min_price:
            continue
        if max_price is not None and hostel.price_min > max_price:
            continue
        hostels_with_distance.append((hostel, distance))

    sort = request.args.get("sort", "nearest")
    if sort == "price":
        hostels_with_distance.sort(key=lambda item: (item[0].price_min, item[1]))
    elif sort == "rating":
        hostels_with_distance.sort(key=lambda item: (-rating_summary(item[0])["average"], item[1]))
    else:
        hostels_with_distance.sort(key=lambda item: item[1])
    return jsonify(
        college={
            "id": college.id,
            "name": college.name,
            "short_name": college.short_name,
            "area": college.area,
            "latitude": college.latitude,
            "longitude": college.longitude,
        },
        radius_km=radius,
        count=len(hostels_with_distance),
        hostels=[hostel_payload(hostel, distance, include_reviews=False) for hostel, distance in hostels_with_distance],
    )


@app.get("/api/hostels/<int:hostel_id>")
def api_hostel_detail(hostel_id: int):
    hostel = Hostel.query.filter_by(id=hostel_id, status="approved").first()
    if not hostel:
        return jsonify(error="That hostel is not available."), 404
    return jsonify(hostel=hostel_payload(hostel))


@app.post("/api/hostels/<int:hostel_id>/reviews")
@login_required
def create_review(hostel_id: int):
    hostel = Hostel.query.filter_by(id=hostel_id, status="approved").first()
    if not hostel:
        return jsonify(error="That hostel is not available."), 404
    if Review.query.filter_by(hostel_id=hostel.id, user_id=g.user.id).first():
        return jsonify(error="You already reviewed this hostel. Edit your existing review instead."), 409
    try:
        values = validate_review_data(request.form.to_dict() if not request.is_json else json_or_form_data())
        review = Review(hostel_id=hostel.id, user_id=g.user.id, **values)
        db.session.add(review)
        db.session.flush()
        for file_storage in request.files.getlist("media"):
            if file_storage and file_storage.filename:
                db.session.add(save_upload(file_storage, hostel.id, review.id))
        db.session.commit()
    except (ValueError, OSError) as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 400
    return jsonify(review=review_payload(review), hostel=hostel_payload(hostel)), 201


@app.put("/api/reviews/<int:review_id>")
@login_required
def edit_review(review_id: int):
    review = db.session.get(Review, review_id)
    if not review or review.status != "visible":
        return jsonify(error="That review is no longer available."), 404
    if review.user_id != g.user.id:
        return jsonify(error="You can only edit your own review."), 403
    try:
        values = validate_review_data(json_or_form_data())
        for key, value in values.items():
            setattr(review, key, value)
        review.updated_at = utc_now()
        for file_storage in request.files.getlist("media"):
            if file_storage and file_storage.filename:
                db.session.add(save_upload(file_storage, review.hostel_id, review.id))
        db.session.commit()
    except (ValueError, OSError) as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 400
    return jsonify(review=review_payload(review), hostel=hostel_payload(review.hostel))


@app.delete("/api/reviews/<int:review_id>")
@login_required
def delete_review(review_id: int):
    review = db.session.get(Review, review_id)
    if not review:
        return jsonify(error="That review is no longer available."), 404
    if review.user_id != g.user.id:
        return jsonify(error="You can only delete your own review."), 403
    for media in list(review.media):
        remove_media_files(media)
    db.session.delete(review)
    db.session.commit()
    return jsonify(ok=True)


@app.post("/api/reviews/<int:review_id>/helpful")
@login_required
def helpful_review(review_id: int):
    review = db.session.get(Review, review_id)
    if not review or review.status != "visible":
        return jsonify(error="That review is no longer available."), 404
    vote = HelpfulVote.query.filter_by(review_id=review.id, user_id=g.user.id).first()
    if vote:
        db.session.delete(vote)
        voted = False
    else:
        db.session.add(HelpfulVote(review_id=review.id, user_id=g.user.id))
        voted = True
    db.session.commit()
    return jsonify(helpful_count=HelpfulVote.query.filter_by(review_id=review.id).count(), voted=voted)


@app.route("/add-hostel", methods=["GET"])
@login_required
def add_hostel_page():
    return render_template("add_hostel.html")


@app.post("/api/hostels")
@login_required
def create_hostel():
    try:
        values = validate_hostel_data(request.form.to_dict())
        college_id = request.form.get("college_id")
        if college_id:
            college_id = parse_int(college_id, "College", 1, 10_000_000)
            if not db.session.get(College, college_id):
                raise ValueError("Choose a valid nearby college.")
        hostel = Hostel(**values, status="pending", is_sample=False, created_by=g.user.id, college_id=college_id or None)
        db.session.add(hostel)
        db.session.flush()
        files = [file_storage for file_storage in request.files.getlist("media") if file_storage and file_storage.filename]
        if len(files) > 8:
            raise ValueError("Add up to 8 photos or videos per listing.")
        for file_storage in files:
            db.session.add(save_upload(file_storage, hostel.id))
        db.session.commit()
    except (ValueError, OSError) as exc:
        db.session.rollback()
        return jsonify(error=str(exc)), 400
    return jsonify(
        message="Your listing was submitted for admin approval.",
        hostel_id=hostel.id,
        status=hostel.status,
    ), 201


@app.route("/admin")
@admin_required
def admin_page():
    pending_hostels = Hostel.query.filter_by(status="pending").order_by(Hostel.created_at.desc()).all()
    recent_reviews = Review.query.order_by(Review.created_at.desc()).limit(30).all()
    recent_media = Media.query.filter_by(is_removed=False).order_by(Media.uploaded_at.desc()).limit(30).all()
    return render_template(
        "admin.html",
        pending_hostels=pending_hostels,
        recent_reviews=recent_reviews,
        recent_media=recent_media,
    )


@app.post("/api/admin/hostels/<int:hostel_id>/status")
@admin_required
def update_hostel_status(hostel_id: int):
    hostel = db.session.get(Hostel, hostel_id)
    if not hostel:
        return jsonify(error="That listing was not found."), 404
    status = str(json_or_form_data().get("status", "")).lower()
    if status not in HOSTEL_STATUSES:
        return jsonify(error="Choose pending, approved, or rejected."), 400
    hostel.status = status
    db.session.commit()
    return jsonify(ok=True, status=status)


@app.delete("/api/admin/reviews/<int:review_id>")
@admin_required
def admin_remove_review(review_id: int):
    review = db.session.get(Review, review_id)
    if not review:
        return jsonify(error="That review was not found."), 404
    review.status = "removed"
    db.session.commit()
    return jsonify(ok=True)


@app.delete("/api/admin/media/<int:media_id>")
@admin_required
def admin_remove_media(media_id: int):
    media = db.session.get(Media, media_id)
    if not media:
        return jsonify(error="That media item was not found."), 404
    media.is_removed = True
    remove_media_files(media)
    db.session.commit()
    return jsonify(ok=True)


with app.app_context():
    seed_database()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=os.environ.get("FLASK_DEBUG") == "1")
