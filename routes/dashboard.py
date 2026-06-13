from flask import Blueprint, request, jsonify, session
from config import users_col, db
from models.user import find_user_by_id, serialize_user
from bson import ObjectId
from datetime import datetime
import base64, re

dashboard_bp = Blueprint("dashboard", __name__)


# ─────────────────────────────────────────────
#  HELPER: login required
# ─────────────────────────────────────────────
def login_required(f):
    import functools
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Please login first"}), 401
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
#  GET DONORS FOR MAP  →  GET /get_donors
#  Called by the Leaflet map in dashboard.html
# ─────────────────────────────────────────────
@dashboard_bp.route("/get_donors", methods=["GET"])
def get_donors():
    blood = request.args.get("blood", "")
    city  = request.args.get("city", "")

    query = {"role": "donor", "available": True, "is_active": True}
    if blood:
        query["blood_group"] = blood
    if city:
        query["city"] = {"$regex": city, "$options": "i"}

    donors = list(users_col.find(query, {
        "name": 1, "blood_group": 1, "city": 1,
        "lat": 1, "lng": 1, "_id": 0
    }))

    # For donors without lat/lng, assign approximate coords by city keyword
    city_coords = {
        "dhaka":       (23.8103, 90.4125),
        "mirpur":      (23.8223, 90.3654),
        "gulshan":     (23.7935, 90.4048),
        "uttara":      (23.8759, 90.3795),
        "dhanmondi":   (23.7465, 90.3760),
        "mohammadpur": (23.7678, 90.3585),
        "banani":      (23.7945, 90.4002),
        "khilgaon":    (23.7521, 90.4256),
        "bashundhara": (23.8221, 90.4285),
        "savar":       (23.8582, 90.2665),
        "shyamoli":    (23.7745, 90.3668),
        "chittagong":  (22.3569, 91.7832),
        "sylhet":      (24.8949, 91.8687),
        "rajshahi":    (24.3745, 88.6042),
        "khulna":      (22.8456, 89.5403),
        "mymensingh":  (24.7471, 90.4203),
        "gazipur":     (23.9984, 90.4125),
        "narayanganj": (23.6238, 90.5000),
        "barisal":     (22.7010, 90.3535),
        "comilla":     (23.4607, 91.1809),
        "rangpur":     (25.7439, 89.2752),
        "jessore":     (23.1664, 89.2081),
    }

    import random
    result = []
    for d in donors:
        if not d.get("lat") or not d.get("lng"):
            city_key = (d.get("city") or "").lower()
            coords = (23.8103, 90.4125)  # default Dhaka
            for key, c in city_coords.items():
                if key in city_key:
                    coords = c
                    break
            # Small random offset so markers don't stack
            d["lat"] = coords[0] + random.uniform(-0.02, 0.02)
            d["lng"] = coords[1] + random.uniform(-0.02, 0.02)
        result.append(d)

    return jsonify(result), 200


# ─────────────────────────────────────────────
#  EMERGENCY REQUEST  →  POST /emergency-request
# ─────────────────────────────────────────────
@dashboard_bp.route("/emergency-request", methods=["POST"])
def emergency_request():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    required = ["patient_name", "blood_group", "hospital", "contact"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    emergency_col = db["emergencies"]

    doc = {
        "patient_name": data.get("patient_name", "").strip(),
        "blood_group":  data.get("blood_group", "").strip(),
        "hospital":     data.get("hospital", "").strip(),
        "contact":      data.get("contact", "").strip(),
        "urgency":      data.get("urgency", "urgent"),
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


# ─────────────────────────────────────────────
#  GET PROFILE  →  GET /dashboard/profile
# ─────────────────────────────────────────────
@dashboard_bp.route("/dashboard/profile", methods=["GET"])
@login_required
def get_profile():
    user = find_user_by_id(session["user_id"])
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"success": True, "user": serialize_user(user)}), 200


# ─────────────────────────────────────────────
@dashboard_bp.route("/dashboard/profile", methods=["PUT"])
@login_required
def update_profile():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    allowed = [
        "name", "phone", "blood_group", "dob", "gender",
        "city", "address", "last_donation", "weight",
        "notes", "available", "role", "age", "division",
        "district", "hospital"
    ]

    update = {k: data[k] for k in allowed if k in data}
    update["updated_at"] = datetime.utcnow()

    users_col.update_one(
        {"_id": ObjectId(session["user_id"])},
        {"$set": update}
    )

    user = find_user_by_id(session["user_id"])

    if not user:
        return jsonify({"error": "User not found"}), 404

    # ── Auto-publish to registry collection ──
    registry_col = db["registry"]
    registry_doc = {
        "fullName":     user.get("name", ""),
        "email":        user.get("email", ""),
        "phone":        user.get("phone", ""),
        "age":          user.get("age", ""),
        "bloodGroup":   user.get("blood_group", ""),
        "role":         user.get("role", "donor"),
        "division":     user.get("division", user.get("city", "Dhaka")),
        "district":     user.get("district", user.get("city", "")),
        "available":    user.get("available", True),
        "lastDonation": user.get("last_donation", ""),
        "notes":        user.get("notes", ""),
        "avatar":       user.get("profile_pic", ""),
        "hasNid":       bool(user.get("nid")),
        "user_id":      session["user_id"],
        "updated_at":   datetime.utcnow(),
    }

    registry_col.update_one(
        {"user_id": session["user_id"]},
        {"$set": registry_doc, "$setOnInsert": {"created_at": datetime.utcnow()}},
        upsert=True
    )

    return jsonify({"success": True, "user": serialize_user(user)}), 200
# ─────────────────────────────────────────────
#  UPLOAD AVATAR  →  POST /dashboard/avatar
#  Receives base64 image, stores in MongoDB
# ─────────────────────────────────────────────
@dashboard_bp.route("/dashboard/avatar", methods=["POST"])
@login_required
def upload_avatar():
    data = request.get_json(silent=True)
    # Accept both 'avatar' and 'image' keys
    image_data = (data or {}).get("avatar") or (data or {}).get("image")
    if not image_data:
        return jsonify({"error": "No image data received"}), 400

    if not image_data.startswith("data:image"):
        return jsonify({"error": "Invalid image format"}), 400

    if len(image_data) > 7 * 1024 * 1024:
        return jsonify({"error": "Image too large. Max 5MB"}), 400

    users_col.update_one(
        {"_id": ObjectId(session["user_id"])},
        {"$set": {"profile_pic": image_data, "updated_at": datetime.utcnow()}}
    )

    # Also update avatar in registry
    registry_col = db["registry"]
    registry_col.update_one(
        {"user_id": session["user_id"]},
        {"$set": {"avatar": image_data}}
    )

    return jsonify({"success": True, "message": "Avatar updated"}), 200

# ─────────────────────────────────────────────
#  GET EMERGENCY REQUESTS (for admin)
#  GET /emergencies
# ─────────────────────────────────────────────
@dashboard_bp.route("/emergencies", methods=["GET"])
def get_emergencies():
    emergency_col = db["emergencies"]
    status = request.args.get("status", "pending")
    query = {}
    if status != "all":
        query["status"] = status

    emergencies = list(emergency_col.find(query).sort("created_at", -1).limit(50))
    for e in emergencies:
        e["_id"] = str(e["_id"])
        if "created_at" in e:
            e["created_at"] = e["created_at"].isoformat()

    return jsonify({"success": True, "emergencies": emergencies}), 200


# ─────────────────────────────────────────────
#  UPDATE EMERGENCY STATUS  →  PATCH /emergencies/<id>
# ─────────────────────────────────────────────
@dashboard_bp.route("/emergencies/<eid>", methods=["PATCH"])
def update_emergency(eid):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("approved", "rejected", "pending"):
        return jsonify({"error": "Invalid status"}), 400

    emergency_col = db["emergencies"]
    try:
        emergency_col.update_one(
            {"_id": ObjectId(eid)},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )
    except Exception:
        return jsonify({"error": "Invalid ID"}), 400

    return jsonify({"success": True, "status": status}), 200


# ─────────────────────────────────────────────
#  GET BLOOD STOCK  →  GET /blood-stock
# ─────────────────────────────────────────────
@dashboard_bp.route("/blood-stock", methods=["GET"])
def blood_stock():
    stock_col = db["blood_stock"]
    stock = list(stock_col.find({}, {"_id": 0}))

    # If no stock data yet, return defaults
    if not stock:
        defaults = [
            {"type": "A+",  "units": 12, "status": "good"},
            {"type": "A-",  "units": 5,  "status": "low"},
            {"type": "B+",  "units": 9,  "status": "good"},
            {"type": "B-",  "units": 3,  "status": "low"},
            {"type": "AB+", "units": 6,  "status": "good"},
            {"type": "AB-", "units": 1,  "status": "critical"},
            {"type": "O+",  "units": 18, "status": "good"},
            {"type": "O-",  "units": 2,  "status": "low"},
        ]
        return jsonify({"success": True, "stock": defaults}), 200

    return jsonify({"success": True, "stock": stock}), 200


# ─────────────────────────────────────────────
#  GET DONATION HISTORY  →  GET /dashboard/history
# ─────────────────────────────────────────────
@dashboard_bp.route("/dashboard/history", methods=["GET"])
@login_required
def donation_history():
    history_col = db["donations"]
    records = list(history_col.find(
        {"donor_id": session["user_id"]},
        {"_id": 0}
    ).sort("date", -1).limit(20))
    return jsonify({"success": True, "history": records}), 200
# ─────────────────────────────────────────────
#  SUBMIT DONATION FOR CERTIFICATE
#  POST /dashboard/donation
# ─────────────────────────────────────────────
@dashboard_bp.route("/dashboard/donation", methods=["POST"])
@login_required
def submit_donation():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    required = ["donation_date", "hospital", "recipient_blood_group"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing: {', '.join(missing)}"}), 400

    donations_col = db["donations"]

    doc = {
        "donor_id":             session["user_id"],
        "donor_name":           data.get("donor_name", ""),
        "donor_blood_group":    data.get("donor_blood_group", ""),
        "donation_date":        data.get("donation_date", ""),
        "hospital":             data.get("hospital", "").strip(),
        "recipient_blood_group": data.get("recipient_blood_group", ""),
        "units":                data.get("units", 1),
        "notes":                data.get("notes", "").strip(),
        "status":               "pending",  # pending → approved/rejected by admin
        "created_at":           datetime.utcnow(),
    }

    result = donations_col.insert_one(doc)
    return jsonify({
        "success": True,
        "message": "Donation submitted for admin approval. Certificate will unlock once approved.",
        "donation_id": str(result.inserted_id)
    }), 201


# ─────────────────────────────────────────────
#  GET MY CERTIFICATE STATUS
#  GET /dashboard/my-certificate
# ─────────────────────────────────────────────
@dashboard_bp.route("/dashboard/my-certificate", methods=["GET"])
@login_required
def my_certificate():
    donations_col = db["donations"]

    # Get all donations for this user
    all_donations = list(donations_col.find(
        {"donor_id": session["user_id"]},
        {"_id": 0, "donor_id": 0}
    ).sort("created_at", -1))

    approved = [d for d in all_donations if d.get("status") == "approved"]
    pending  = [d for d in all_donations if d.get("status") == "pending"]

    return jsonify({
        "success":          True,
        "approved_count":   len(approved),
        "pending_count":    len(pending),
        "latest_approved":  approved[0] if approved else None,
        "has_certificate":  len(approved) > 0,
    }), 200