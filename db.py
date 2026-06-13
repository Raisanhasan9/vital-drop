from pymongo import MongoClient
import os

# MongoDB connection URL
MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://localhost:27017/"
)

# Connect MongoDB
client = MongoClient(MONGO_URI)

# Database
db = client["vitaldrop"]

# Collections
users_col = db["users"]
tickets_col = db["tickets"]
messages_col = db["messages"]

print("✅ MongoDB Connected")