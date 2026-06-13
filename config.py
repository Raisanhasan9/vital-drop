import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI   = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME     = os.getenv("DB_NAME", "vitaldrop")
SECRET_KEY  = os.getenv("SECRET_KEY", "vitaldrop_secret")

client = MongoClient(MONGO_URI)
db     = client[DB_NAME]

# Collections
users_col  = db["users"]       # donors & receivers
admins_col = db["admins"]      # admin accounts