from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from decouple import config
from starlette.responses import RedirectResponse

app = FastAPI()

# Retrieve MongoDB URI from environment variable
mongo_uri = "mongodb+srv://xohack:w4BRF5QXTHUcbCPE@xohack-cluster.0asnq.mongodb.net/?retryWrites=true&w=majority&appName=xohack-cluster"

# Setup MongoDB connection
client = MongoClient(mongo_uri)
db = client["auth_db"]
users_collection = db["users"]

# Define response model for LinkedIn data
class LinkedInData(BaseModel):
    # Define the expected structure for LinkedIn data
    profile_url: str
    experience: str
    skills: list[str]
    # You can extend this as needed

@app.get("/")
async def root():
    return RedirectResponse("/docs")

@app.get("/profile/{email}")
def fetch_linked_in_data(email: str):
    user = users_collection.find_one({"email": email})
    if user:
        linked_in_data = user.get("linked_in_data")
        if linked_in_data:
            return linked_in_data  # Return the LinkedIn data
        else:
            raise HTTPException(status_code=404, detail="LinkedIn data not found")
    else:
        raise HTTPException(status_code=404, detail="User not found")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)