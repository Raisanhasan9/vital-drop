from flask import Flask, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
from config import SECRET_KEY

# ── Blueprints
from routes.auth      import auth_bp
from routes.admin     import admin_bp
from routes.dashboard import dashboard_bp
from routes.registry  import registry_bp
from routes.general   import general_bp

app = Flask(__name__, template_folder="templates")

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
app.secret_key = SECRET_KEY
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"]   = False

# ─────────────────────────────────────────────
#  CORS
# ─────────────────────────────────────────────
CORS(app,
     resources={r"/*": {"origins": [
         "http://127.0.0.1:5500",
         "http://localhost:5500",
         "http://127.0.0.1:5000",
         "http://localhost:5000",
         "null"
     ]}},
     supports_credentials=True)

# ─────────────────────────────────────────────
#  REGISTER BLUEPRINTS
# ─────────────────────────────────────────────
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(registry_bp)
app.register_blueprint(general_bp)

# ─────────────────────────────────────────────
#  PAGE ROUTES (serve HTML files)
# ─────────────────────────────────────────────
@app.route("/")
@app.route("/login")
def login_page():
    if session.get("logged_in"):
        if session.get("user_role") == "admin":
            return redirect(url_for("admin_dashboard_page"))
        return redirect(url_for("dashboard_page"))
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/dashboard")
def dashboard_page():
    if not session.get("logged_in"):
        return redirect(url_for("login_page"))
    if session.get("user_role") == "admin":
        return redirect(url_for("admin_dashboard_page"))
    return render_template("dashboard.html")

@app.route("/admin/dashboard")
def admin_dashboard_page():
    if not session.get("logged_in") or session.get("user_role") != "admin":
        return redirect(url_for("login_page"))
    return render_template("dashboardadmin.html")

@app.route("/emergency")
def emergency_page():
    return render_template("emergency.html")

@app.route("/guide")
def guide_page():
    return render_template("guide.html")

@app.route("/registry")
@app.route("/registery")
def registry_page():
    return render_template("registery.html")

@app.route("/about")
def about_page():
    return render_template("about.html")

@app.route("/index")
def index_page():
    return render_template("index.html")

@app.route("/thankyou")
def thankyou_page():
    session.clear()
    return render_template("thankyou.html")

# ─────────────────────────────────────────────
#  HEALTH CHECK
# ─────────────────────────────────────────────
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "VitalDrop API running", "version": "1.0"}), 200

# ─────────────────────────────────────────────
#  AUTO SEED ADMIN ON STARTUP
# ─────────────────────────────────────────────
def seed_default_admin():
    from config import admins_col
    from models.user import create_admin
    existing = admins_col.find_one({"email": "admin@vitaldrop.com"})
    if not existing:
        try:
            create_admin("admin@vitaldrop.com", "Admin@1234", "Super Admin")
            print("✅ Admin created: admin@vitaldrop.com / Admin@1234")
        except Exception as e:
            print(f"Admin seed skipped: {e}")

if __name__ == "__main__":
    seed_default_admin()
    app.run(debug=True, host="0.0.0.0", port=5000)