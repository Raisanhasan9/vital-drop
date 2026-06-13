from flask import Blueprint, request, jsonify, session
from models.user import (
    create_user, find_user_by_email,
    verify_password, serialize_user
)

auth_bp = Blueprint("auth", __name__)


# ─────────────────────────────────────────────
#  REGISTER  →  POST /api/register
# ─────────────────────────────────────────────
@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    required = ["name", "email", "phone", "nid", "city", "blood_group", "password", "role"]
    missing = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    if len(data["password"]) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    if data.get("role") not in ("donor", "receiver"):
        return jsonify({"error": "Invalid role. Must be donor or receiver"}), 400

    try:
        user = create_user(data)
        return jsonify({"success": True, "message": "Registration successful", "user": user}), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        print(f"[REGISTER ERROR] {e}")
        return jsonify({"error": "Server error during registration"}), 500


# ─────────────────────────────────────────────
#  USER LOGIN  →  POST /api/login
# ─────────────────────────────────────────────
@auth_bp.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "No data received"}), 400

        email    = data.get("email", "").strip()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        user = find_user_by_email(email)

        if not user or not verify_password(password, user["password"]):
            return jsonify({"error": "Invalid email or password"}), 401

        if not user.get("is_active", True):
            return jsonify({"error": "Account is deactivated. Contact support."}), 403

        session["user_id"]    = str(user["_id"])
        session["user_email"] = user["email"]
        session["user_role"]  = user.get("role", "donor")
        session["logged_in"]  = True

        return jsonify({
            "success": True,
            "message": "Login successful",
            "user":    serialize_user(user),
            "role":    user.get("role", "donor")
        }), 200

    except Exception as e:
        print(f"[LOGIN ERROR] {e}")
        return jsonify({"error": "Server error during login", "detail": str(e)}), 500

# ─────────────────────────────────────────────
#  LOGOUT  →  POST /api/logout
# ─────────────────────────────────────────────
@auth_bp.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out"}), 200


# ─────────────────────────────────────────────
#  GET CURRENT USER  →  GET /api/me
# ─────────────────────────────────────────────
@auth_bp.route("/api/me", methods=["GET"])
def me():
    if not session.get("logged_in"):
        return jsonify({"error": "Not authenticated"}), 401

    from models.user import find_user_by_id, find_admin_by_email

    if session.get("user_role") == "admin":
        admin = find_admin_by_email(session.get("user_email"))
        if not admin:
            return jsonify({"error": "Admin not found"}), 404
        return jsonify({"success": True, "user": serialize_user(admin)}), 200
    else:
        user = find_user_by_id(session["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify({"success": True, "user": serialize_user(user)}), 200