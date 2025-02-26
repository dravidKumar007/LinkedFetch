from decouple import config
from pymongo import MongoClient

client = MongoClient(config("MONGO_URI"))
db = client["auth_db"]
users_collection = db["users"]
