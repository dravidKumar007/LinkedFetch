from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from decouple import config
from starlette.responses import RedirectResponse
from questions import router as questions_router
from auth import router as auth_router
from linkedin import router as Linked_in_router
from Resume import router as Resume_router


app = FastAPI()

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)

app.include_router(questions_router)
app.include_router(auth_router)
app.include_router(Linked_in_router)
app.include_router(Resume_router)

# Retrieve MongoDB URI from environment variable
mongo_uri = "mongodb+srv://xohack:w4BRF5QXTHUcbCPE@xohack-cluster.0asnq.mongodb.net/?retryWrites=true&w=majority&appName=xohack-cluster"

# Setup MongoDB connection
client = MongoClient(mongo_uri)
db = client["auth_db"]
users_collection = db["users"]

# Define response model for LinkedIn data
class LinkedInData(BaseModel):
    profile_url: str
    experience: str
    skills: list[str]

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
