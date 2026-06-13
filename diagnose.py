"""
Run this to diagnose your setup.
Usage: python diagnose.py
"""
print("=" * 50)
print("VitalDrop Diagnostic Tool")
print("=" * 50)

# Test 1: pymongo
try:
    from pymongo import MongoClient
    print("✅ pymongo installed")
except ImportError:
    print("❌ pymongo NOT installed — run: pip install pymongo")
    exit()

# Test 2: bcrypt
try:
    import bcrypt
    pw = bcrypt.hashpw(b"test", bcrypt.gensalt())
    print("✅ bcrypt installed and working")
except ImportError:
    print("❌ bcrypt NOT installed — run: pip install bcrypt")
    exit()

# Test 3: MongoDB connection
try:
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000)
    client.server_info()
    print("✅ MongoDB is running and reachable")
except Exception as e:
    print(f"❌ MongoDB NOT reachable: {e}")
    print("   → Open MongoDB Compass and click Connect first!")
    exit()

# Test 4: Write to DB
try:
    db = client["vitaldrop_test"]
    db["test_col"].insert_one({"test": True})
    db["test_col"].delete_many({"test": True})
    print("✅ MongoDB read/write working")
except Exception as e:
    print(f"❌ MongoDB write failed: {e}")
    exit()

# Test 5: dotenv
try:
    from dotenv import load_dotenv
    print("✅ python-dotenv installed")
except ImportError:
    print("❌ python-dotenv NOT installed — run: pip install python-dotenv")

print("=" * 50)
print("✅ All checks passed! Your setup is ready.")
print("   Now run: python app.py")
print("=" * 50)