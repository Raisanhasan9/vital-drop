from flask import Blueprint, request, jsonify, session
from models.user import (
    find_admin_by_email, verify_password,
    serialize_user, create_admin
)
from config import users_col, admins_col
from bson import ObjectId
from datetime import datetime
import functools

admin_bp = Blueprint("admin", __name__)


# ─────────────────────────────────────────────
#  DECORATOR: require admin session
# ─────────────────────────────────────────────
def admin_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in") or session.get("user_role") != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return wrapper


# ─────────────────────────────────────────────
#  ADMIN LOGIN  →  POST /admin_login
# ─────────────────────────────────────────────
@admin_bp.route("/api/admin_login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    email    = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    admin = find_admin_by_email(email)
    if not admin or not verify_password(password, admin["password"]):
        return jsonify({"error": "Invalid admin credentials"}), 401

    # ── Create admin session
    session["user_id"]    = str(admin["_id"])
    session["user_email"] = admin["email"]
    session["user_role"]  = "admin"
    session["logged_in"]  = True

    return jsonify({
        "success": True,
        "message": "Admin login successful",
        "user":    serialize_user(admin),
        "role":    "admin"
    }), 200


# ─────────────────────────────────────────────
#  GET ALL USERS  →  GET /admin/users
# ─────────────────────────────────────────────
@admin_bp.route("/admin/users", methods=["GET"])
@admin_required
def get_all_users():
    users = list(users_col.find({}))
    safe  = [serialize_user(u) for u in users]
    return jsonify({"success": True, "users": safe, "count": len(safe)}), 200


# ─────────────────────────────────────────────
#  GET SINGLE USER  →  GET /admin/users/<id>
# ─────────────────────────────────────────────
@admin_bp.route("/admin/users/<user_id>", methods=["GET"])
@admin_required
def get_user(user_id):
    try:
        user = users_col.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return jsonify({"error": "Invalid user ID"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"success": True, "user": serialize_user(user)}), 200


# ─────────────────────────────────────────────
#  DELETE USER  →  DELETE /admin/users/<id>
# ─────────────────────────────────────────────
@admin_bp.route("/admin/users/<user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    try:
        result = users_col.delete_one({"_id": ObjectId(user_id)})
    except Exception:
        return jsonify({"error": "Invalid user ID"}), 400

    if result.deleted_count == 0:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"success": True, "message": "User deleted"}), 200


# ─────────────────────────────────────────────
#  TOGGLE USER ACTIVE  →  PATCH /admin/users/<id>/toggle
# ─────────────────────────────────────────────
@admin_bp.route("/admin/users/<user_id>/toggle", methods=["PATCH"])
@admin_required
def toggle_user(user_id):
    try:
        user = users_col.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return jsonify({"error": "Invalid user ID"}), 400

    if not user:
        return jsonify({"error": "User not found"}), 404

    new_status = not user.get("is_active", True)
    users_col.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": new_status, "updated_at": datetime.utcnow()}}
    )
    return jsonify({"success": True, "is_active": new_status}), 200


# ─────────────────────────────────────────────
#  DASHBOARD STATS  →  GET /admin/stats
# ─────────────────────────────────────────────
@admin_bp.route("/admin/stats", methods=["GET"])
@admin_required
def stats():
    total_users    = users_col.count_documents({})
    total_donors   = users_col.count_documents({"role": "donor"})
    total_receivers= users_col.count_documents({"role": "receiver"})
    available_now  = users_col.count_documents({"role": "donor", "available": True})

    # Blood group breakdown
    pipeline = [{"$group": {"_id": "$blood_group", "count": {"$sum": 1}}}]
    blood_groups = {r["_id"]: r["count"] for r in users_col.aggregate(pipeline) if r["_id"]}

    return jsonify({
        "success":        True,
        "total_users":    total_users,
        "total_donors":   total_donors,
        "total_receivers":total_receivers,
        "available_now":  available_now,
        "blood_groups":   blood_groups,
    }), 200


# ─────────────────────────────────────────────
#  SEED FIRST ADMIN  →  POST /admin/seed
#  (Disable this route after first use!)
# ─────────────────────────────────────────────
@admin_bp.route("/admin/seed", methods=["POST"])
def seed_admin():
    data = request.get_json(silent=True) or {}
    email    = data.get("email", "admin@vitaldrop.com")
    password = data.get("password", "Admin@1234")
    name     = data.get("name", "Super Admin")

    try:
        admin = create_admin(email, password, name)
        return jsonify({"success": True, "message": "Admin created", "admin": admin}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    # ─────────────────────────────────────────────
#  GET PENDING DONATIONS  →  GET /admin/donations
# ─────────────────────────────────────────────
@admin_bp.route("/admin/donations", methods=["GET"])
@admin_required
def admin_get_donations():
    from config import db
    donations_col = db["donations"]
    status = request.args.get("status", "pending")
    query = {} if status == "all" else {"status": status}
    donations = list(donations_col.find(query).sort("created_at", -1).limit(100))
    for d in donations:
        d["_id"] = str(d["_id"])
        if "created_at" in d:
            d["created_at"] = d["created_at"].isoformat()
    return jsonify({"success": True, "donations": donations, "count": len(donations)}), 200


# ─────────────────────────────────────────────
#  APPROVE/REJECT DONATION  →  PATCH /admin/donations/<id>
# ─────────────────────────────────────────────
@admin_bp.route("/admin/donations/<did>", methods=["PATCH"])
@admin_required
def admin_update_donation(did):
    from config import db
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("approved", "rejected", "pending"):
        return jsonify({"error": "Invalid status"}), 400
    donations_col = db["donations"]
    try:
        donations_col.update_one(
            {"_id": ObjectId(did)},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )
    except Exception:
        return jsonify({"error": "Invalid ID"}), 400
    return jsonify({"success": True, "status": status}), 200
# ─────────────────────────────────────────────
#  GET PENDING DONATIONS  →  GET /admin/donations
# ─────────────────────────────────────────────
@admin_bp.route("/admin/donations", methods=["GET"])
@admin_required
def get_donations():
    from config import db
    donations_col = db["donations"]
    status = request.args.get("status", "pending")
    query = {} if status == "all" else {"status": status}
    donations = list(donations_col.find(query).sort("created_at", -1).limit(100))
    for d in donations:
        d["_id"] = str(d["_id"])
        if "created_at" in d:
            d["created_at"] = d["created_at"].isoformat()
    return jsonify({"success": True, "donations": donations, "count": len(donations)}), 200


# ─────────────────────────────────────────────
#  APPROVE/REJECT DONATION  →  PATCH /admin/donations/<id>
# ─────────────────────────────────────────────
@admin_bp.route("/admin/donations/<did>", methods=["PATCH"])
@admin_required
def update_donation(did):
    from config import db
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in ("approved", "rejected", "pending"):
        return jsonify({"error": "Invalid status"}), 400
    donations_col = db["donations"]
    try:
        donations_col.update_one(
            {"_id": ObjectId(did)},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}}
        )
    except Exception:
        return jsonify({"error": "Invalid ID"}), 400
    return jsonify({"success": True, "status": status}), 200