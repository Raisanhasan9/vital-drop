from datetime import datetime
from bson import ObjectId
from config import users_col, admins_col
import bcrypt


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify plain password against stored bcrypt hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def serialize_user(doc: dict) -> dict:
    """Convert MongoDB doc to JSON-safe dict (removes password, converts ObjectId)."""
    if not doc:
        return {}
    safe = {k: v for k, v in doc.items() if k != "password"}
    safe["_id"] = str(doc["_id"])
    return safe


# ─────────────────────────────────────────────
#  USER OPERATIONS
# ─────────────────────────────────────────────

def create_user(data: dict) -> dict:
    """
    Insert a new user (donor/receiver) into the database.
    Returns the created user doc (without password).
    """
    # Check duplicate email
    if users_col.find_one({"email": data["email"].lower().strip()}):
        raise ValueError("Email already registered.")

    # Check duplicate NID
    if data.get("nid") and users_col.find_one({"nid": data["nid"].strip()}):
        raise ValueError("NID already registered.")

    user_doc = {
        # ── Personal
        "name":          data.get("name", "").strip(),
        "email":         data.get("email", "").lower().strip(),
        "phone":         data.get("phone", "").strip(),
        "nid":           data.get("nid", "").strip(),
        "dob":           data.get("dob", ""),
        "gender":        data.get("gender", ""),
        "city":          data.get("city", "").strip(),
        "address":       data.get("address", "").strip(),
        # ── Medical
        "blood_group":   data.get("blood_group", ""),
        "weight":        data.get("weight", ""),
        "last_donation": data.get("last_donation", ""),
        "hospital":      data.get("hospital", "").strip(),
        "notes":         data.get("notes", "").strip(),
        "available":     data.get("available", True),
        # ── Account
        "role":          data.get("role", "donor"),   # donor | receiver
        "profile_pic":   None,                         # stored later
        "password":      hash_password(data["password"]),
        "is_active":     True,
        "created_at":    datetime.utcnow(),
        "updated_at":    datetime.utcnow(),
    }

    result = users_col.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id
    return serialize_user(user_doc)


def find_user_by_email(email: str):
    """Find a user document by email (case-insensitive)."""
    return users_col.find_one({"email": email.lower().strip()})


def find_user_by_id(user_id: str):
    """Find a user by ObjectId string."""
    try:
        return users_col.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None


# ─────────────────────────────────────────────
#  ADMIN OPERATIONS
# ─────────────────────────────────────────────

def create_admin(email: str, password: str, name: str = "Admin") -> dict:
    """Create an admin account (call this once via seed script)."""
    if admins_col.find_one({"email": email.lower().strip()}):
        raise ValueError("Admin email already exists.")

    doc = {
        "name":       name,
        "email":      email.lower().strip(),
        "password":   hash_password(password),
        "role":       "admin",
        "created_at": datetime.utcnow(),
    }
    result = admins_col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_user(doc)


def find_admin_by_email(email: str):
    """Find admin doc by email."""
    return admins_col.find_one({"email": email.lower().strip()})