from flask import Blueprint, request, jsonify, session
from config import db, users_col
from bson import ObjectId
from datetime import datetime
import functools

registry_bp = Blueprint("registry", __name__)

emergency_col = db["emergencies"]
registry_col  = db["registry"]   # separate public registry profiles


# ─────────────────────────────────────────────
#  HELPER
# ─────────────────────────────────────────────
def fmt_time(dt):
    """Convert datetime to human-readable 'X min ago' string."""
    if not dt:
        return "Recently"
    diff = datetime.utcnow() - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds} sec ago"
    elif seconds < 3600:
        return f"{seconds//60} min ago"
    elif seconds < 86400:
        return f"{seconds//3600} hr ago"
    else:
        return f"{seconds//86400} days ago"


def serialize_emergency(doc):
    doc["id"]  = str(doc["_id"])
    doc["_id"] = str(doc["_id"])
    if "created_at" in doc:
        doc["time"] = fmt_time(doc["created_at"])
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


def serialize_profile(doc):
    doc["id"]  = str(doc["_id"])
    doc["_id"] = str(doc["_id"])
    if "created_at" in doc:
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


# ═══════════════════════════════════════════
#  EMERGENCY FEED
# ═══════════════════════════════════════════

# GET /get-emergency-requests  ← called by emergency.html every 5s
@registry_bp.route("/get-emergency-requests", methods=["GET"])
def get_emergency_requests():
    urgency = request.args.get("urgency", "")
    blood   = request.args.get("blood", "")

    query = {"status": "pending"}
    if urgency:
        query["urgency"] = {"$regex": urgency, "$options": "i"}
    if blood:
        query["blood_group"] = blood.replace("−", "-")

    docs = list(emergency_col.find(query).sort("created_at", -1).limit(50))
    result = [serialize_emergency(d) for d in docs]
    return jsonify(result), 200


# POST /emergency-request  ← called by dashboard.html form
# (already in dashboard.py but also aliased here for completeness)
@registry_bp.route("/emergency-request", methods=["POST"])
def submit_emergency():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    required = ["patient_name", "blood_group", "hospital", "contact"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    doc = {
        "patient_name": data.get("patient_name", "").strip(),
        "blood_group":  data.get("blood_group", "").strip().replace("−", "-"),
        "hospital":     data.get("hospital", "").strip(),
        "contact":      data.get("contact", "").strip(),
        "urgency":      data.get("urgency", "urgent").capitalize(),
        "notes":        data.get("notes", "").strip(),
        "nid":          data.get("nid", "").strip(),
        "created_by":   data.get("created_by", "Guest"),
        "requested_by_user_id": session.get("user_id"),
        "status":       "pending",
        "created_at":   datetime.utcnow(),
    }

    result = emergency_col.insert_one(doc)
    return jsonify({
        "success": True,
        "message": "Emergency request submitted. Donors are being notified.",
        "request_id": str(result.inserted_id)
    }), 201


# ═══════════════════════════════════════════
#  PUBLIC REGISTRY (Donor & Receiver cards)
# ═══════════════════════════════════════════

# GET /registry/profiles  ← load all cards
@registry_bp.route("/registry/profiles", methods=["GET"])
def get_profiles():
    role   = request.args.get("role", "")      # donor | receiver | ""
    blood  = request.args.get("blood", "")
    div    = request.args.get("division", "")
    search = request.args.get("q", "")

    query = {}
    if role:
        query["role"] = role
    if blood:
        query["bloodGroup"] = blood
    if div:
        query["division"] = div
    if search:
        query["$or"] = [
            {"fullName": {"$regex": search, "$options": "i"}},
            {"phone":    {"$regex": search, "$options": "i"}},
            {"district": {"$regex": search, "$options": "i"}},
        ]

    docs = list(registry_col.find(query).sort("created_at", -1).limit(200))
    result = [serialize_profile(d) for d in docs]
    return jsonify({"success": True, "profiles": result, "count": len(result)}), 200


# POST /registry/profile  ← add new profile (with avatar + NID as base64)
@registry_bp.route("/registry/profile", methods=["POST"])
def add_profile():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    required = ["fullName", "phone", "bloodGroup", "role"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    # Check duplicate phone
    if registry_col.find_one({"phone": data["phone"].strip()}):
        return jsonify({"error": "Phone number already registered in registry"}), 409

    # Avatar size check (~5MB)
    avatar = data.get("avatar", "")
    if avatar and len(avatar) > 7 * 1024 * 1024:
        return jsonify({"error": "Avatar image too large. Max 5MB"}), 400

    # NID size check
    nid_image = data.get("nidImage", "")
    if nid_image and len(nid_image) > 7 * 1024 * 1024:
        return jsonify({"error": "NID image too large. Max 5MB"}), 400

    doc = {
        "fullName":     data.get("fullName", "").strip(),
        "email":        data.get("email", "").strip().lower(),
        "phone":        data.get("phone", "").strip(),
        "age":          data.get("age", ""),
        "bloodGroup":   data.get("bloodGroup", "").strip(),
        "role":         data.get("role", "donor"),
        "division":     data.get("division", "Dhaka"),
        "district":     data.get("district", "").strip(),
        "available":    data.get("available", True),
        "lastDonation": data.get("lastDonation", ""),
        "notes":        data.get("notes", "").strip(),
        "avatar":       avatar,
        "nidImage":     nid_image,
        "hasNid":       bool(nid_image),
        "created_at":   datetime.utcnow(),
        "updated_at":   datetime.utcnow(),
    }

    result = registry_col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"success": True, "profile": serialize_profile(doc)}), 201


# PUT /registry/profile/<id>  ← edit existing profile
@registry_bp.route("/registry/profile/<pid>", methods=["PUT"])
def update_profile(pid):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    allowed = [
        "fullName", "email", "phone", "age", "bloodGroup", "role",
        "division", "district", "available", "lastDonation",
        "notes", "avatar", "nidImage"
    ]
    update = {k: data[k] for k in allowed if k in data}
    if "nidImage" in update:
        update["hasNid"] = bool(update["nidImage"])
    update["updated_at"] = datetime.utcnow()

    try:
        registry_col.update_one({"_id": ObjectId(pid)}, {"$set": update})
    except Exception:
        return jsonify({"error": "Invalid profile ID"}), 400

    doc = registry_col.find_one({"_id": ObjectId(pid)})
    return jsonify({"success": True, "profile": serialize_profile(doc)}), 200


# DELETE /registry/profile/<id>  ← remove profile
@registry_bp.route("/registry/profile/<pid>", methods=["DELETE"])
def delete_profile(pid):
    try:
        result = registry_col.delete_one({"_id": ObjectId(pid)})
    except Exception:
        return jsonify({"error": "Invalid profile ID"}), 400

    if result.deleted_count == 0:
        return jsonify({"error": "Profile not found"}), 404

    return jsonify({"success": True, "message": "Profile deleted"}), 200


# GET /registry/stats  ← hero stats on registry page
@registry_bp.route("/registry/stats", methods=["GET"])
def registry_stats():
    total     = registry_col.count_documents({})
    donors    = registry_col.count_documents({"role": "donor"})
    receivers = registry_col.count_documents({"role": "receiver"})
    available = registry_col.count_documents({"available": True})
    return jsonify({
        "success":   True,
        "total":     total,
        "donors":    donors,
        "receivers": receivers,
        "available": available,
    }), 200