from flask import Blueprint, request, jsonify, session
from config import db, users_col
from datetime import datetime

general_bp = Blueprint("general", __name__)


# ─────────────────────────────────────────────
#  PUBLIC STATS  →  GET /stats
#  Used by index.html, thankyou.html counters
# ─────────────────────────────────────────────
@general_bp.route("/stats", methods=["GET"])
def public_stats():
    try:
        donors    = users_col.count_documents({"role": "donor"})
        receivers = users_col.count_documents({"role": "receiver"})
        available = users_col.count_documents({"role": "donor", "available": True})
        emergency_col = db["emergencies"]
        pending   = emergency_col.count_documents({"status": "pending"})

        # Blood group breakdown
        pipeline = [{"$group": {"_id": "$blood_group", "count": {"$sum": 1}}}]
        blood_groups = {
            r["_id"]: r["count"]
            for r in users_col.aggregate(pipeline) if r["_id"]
        }

        return jsonify({
            "success":        True,
            "total_donors":   donors,
            "total_receivers":receivers,
            "available_now":  available,
            "total_users":    donors + receivers,
            "pending_emergency": pending,
            "blood_groups":   blood_groups,
            # Static milestone stats shown on frontend
            "lives_saved":    donors * 3,
            "districts":      64,
            "response_rate":  98.4,
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
#  CONTACT / FEEDBACK  →  POST /contact
#  For any contact form if added later
# ─────────────────────────────────────────────
@general_bp.route("/contact", methods=["POST"])
def contact():
    data = request.get_json(silent=True) or {}
    name    = data.get("name", "").strip()
    email   = data.get("email", "").strip()
    message = data.get("message", "").strip()

    if not name or not email or not message:
        return jsonify({"error": "Name, email, and message are required"}), 400

    contact_col = db["contacts"]
    contact_col.insert_one({
        "name":       name,
        "email":      email,
        "message":    message,
        "created_at": datetime.utcnow(),
    })

    return jsonify({"success": True, "message": "Message received. We'll be in touch!"}), 201


# ─────────────────────────────────────────────
#  LEADERBOARD  →  GET /leaderboard
#  Top donors by donation count
# ─────────────────────────────────────────────
@general_bp.route("/leaderboard", methods=["GET"])
def leaderboard():
    donations_col = db["donations"]
    pipeline = [
        {"$group": {"_id": "$donor_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 15}
    ]
    results = list(donations_col.aggregate(pipeline))

    leaderboard = []
    for i, r in enumerate(results):
        user = users_col.find_one(
            {"_id": r["_id"]},
            {"name": 1, "blood_group": 1, "city": 1}
        )
        if user:
            leaderboard.append({
                "rank":        i + 1,
                "name":        user.get("name", "Anonymous"),
                "blood_group": user.get("blood_group", ""),
                "city":        user.get("city", ""),
                "donations":   r["count"],
                "badge":       _badge(r["count"]),
            })

    return jsonify({"success": True, "leaderboard": leaderboard}), 200


def _badge(count):
    if count >= 10: return "🏆 Legend"
    if count >= 7:  return "🥈 Champion"
    if count >= 4:  return "🥉 Hero"
    if count >= 2:  return "⭐ Donor"
    return "🩸 Member"


# ─────────────────────────────────────────────
#  BLOOD STOCK  →  GET /blood-stock
#  (also in dashboard.py — kept here as alias)
# ─────────────────────────────────────────────
@general_bp.route("/blood-stock", methods=["GET"])
def blood_stock():
    stock_col = db["blood_stock"]
    stock = list(stock_col.find({}, {"_id": 0}))

    if not stock:
        # Default values if no stock data yet
        stock = [
            {"type": "A+",  "units": 12, "status": "good"},
            {"type": "A-",  "units": 5,  "status": "low"},
            {"type": "B+",  "units": 9,  "status": "good"},
            {"type": "B-",  "units": 3,  "status": "low"},
            {"type": "AB+", "units": 6,  "status": "good"},
            {"type": "AB-", "units": 1,  "status": "critical"},
            {"type": "O+",  "units": 18, "status": "good"},
            {"type": "O-",  "units": 2,  "status": "low"},
        ]

    return jsonify({"success": True, "stock": stock}), 200


# ─────────────────────────────────────────────
#  UPDATE BLOOD STOCK (admin)  →  PUT /blood-stock
# ─────────────────────────────────────────────
@general_bp.route("/blood-stock", methods=["PUT"])
def update_blood_stock():
    if not session.get("logged_in") or session.get("user_role") != "admin":
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json(silent=True) or {}
    blood_type = data.get("type")
    units      = data.get("units")

    if not blood_type or units is None:
        return jsonify({"error": "type and units required"}), 400

    # Determine status
    status = "critical" if units <= 2 else "low" if units <= 5 else "good"

    stock_col = db["blood_stock"]
    stock_col.update_one(
        {"type": blood_type},
        {"$set": {"units": units, "status": status, "updated_at": datetime.utcnow()}},
        upsert=True
    )

    return jsonify({"success": True, "type": blood_type, "units": units, "status": status}), 200