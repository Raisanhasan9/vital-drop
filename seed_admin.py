"""
Run this ONCE to create your first admin account.
Usage:  python seed_admin.py

After running, delete or disable this file!
"""
from models.user import create_admin

EMAIL    = "admin@vitaldrop.com"
PASSWORD = "1234567"      # ← CHANGE THIS!
NAME     = "Super Admin"

if __name__ == "__main__":
    try:
        admin = create_admin(EMAIL, PASSWORD, NAME)
        print(f"✅ Admin created successfully!")
        print(f"   Email   : {EMAIL}")
        print(f"   Password: {PASSWORD}")
        print(f"   ID      : {admin['_id']}")
        print(f"\n⚠️  Please change your password after first login!")
    except ValueError as e:
        print(f"⚠️  {e}")
    except Exception as e:
        print(f"❌ Error: {e}")