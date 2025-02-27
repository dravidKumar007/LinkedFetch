import logging

import bcrypt
import time
import jwt
import requests
from decouple import config
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from mongo import users_collection




SECRET_KEY =config("JWT_SECRET_KEY")

router = APIRouter(prefix="/auth", tags=["auth"])

class UserSignUp(BaseModel):
    email: str
    password: str
    linked_in_url: str

class UserLogin(BaseModel):
    email: str
    password: str

class LinkedInLogin(BaseModel):
    email: str
    linked_in_url: str

def hash_password(password: str):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt)

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode(), hashed_password)

def create_jwt(email: str):
    payload = {"email": email, "exp": time.time() + 3600}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def fetch_linked_in_data(linked_in_url: str):
    # Adjust API URL to accept the query parameter 'url'
    api_url = "https://nubela.co/proxycurl/api/v2/linkedin"  # Adjust API URL without embedding LinkedIn URL in path

    # Append the LinkedIn URL as a query parameter
    params = {"url": linked_in_url}

    headers = {
        "Authorization": "Bearer SCHyqcvtE_JyodZvD2-uag"  # Use the actual API key
    }

    try:
        # Send the GET request with query parameter
        response = requests.get(api_url, headers=headers, params=params)
        response.raise_for_status()  # Raise an exception for 4xx/5xx responses
        data = response.json()
        # Return the fetched LinkedIn data
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching LinkedIn data for {linked_in_url}: {e}")
        return None



@router.post("/signup")
def signup(user: UserSignUp):
    existing_user = users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Handle LinkedIn URL without throwing an error
    linked_in_data = None
    if user.linked_in_url:
        try:
            # Fetch LinkedIn data using Proxycurl API or any other service
            linked_in_data = fetch_linked_in_data(user.linked_in_url)
            if linked_in_data:
                # Log the successful fetching of LinkedIn data
                logging.info(f"Successfully fetched LinkedIn data for {user.linked_in_url}")
            else:
                logging.warning(f"No LinkedIn data found for {user.linked_in_url}")
        except Exception as e:
            logging.error(f"Error processing LinkedIn URL {user.linked_in_url}: {e}")
            # Continue signup process even if LinkedIn data fetch fails

    # Store user data along with LinkedIn data (if fetched)
    hashed_password = hash_password(user.password)
    user_data = {
        "email": user.email,
        "password": hashed_password,
        "linked_in": user.linked_in_url,
        "linked_in_data": linked_in_data  # Storing the fetched LinkedIn data
    }
    users_collection.insert_one(user_data)

    return {"message": "User registered successfully"}

@router.post("/login")
def login(user: UserLogin):
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_jwt(user.email)
    return {"token": token}

def verify_jwt(token: str):
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["SHA256"])
        return decoded_token
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/verify-token")
def verify_token(token: str):
    """Verifies JWT token"""
    return {"message": "Token is valid", "user": verify_jwt(token)}

@router.post("/linkedin_login")
def addLinkedIn(user:LinkedInLogin):
    linked_in_data = None
    if user.linked_in_url:
        try:
            # Fetch LinkedIn data using Proxycurl API or any other service
            linked_in_data = fetch_linked_in_data(user.linked_in_url)
            print(linked_in_data)
            if linked_in_data:
                # Log the successful fetching of LinkedIn data
                logging.info(f"Successfully fetched LinkedIn data for {user.linked_in_url}")
            else:
                logging.warning(f"No LinkedIn data found for {user.linked_in_url}")
                raise HTTPException(status_code=404,detail="No LinkedIn data found for {user.linked_in_url}")
        except Exception as e:
            logging.error(f"Error processing LinkedIn URL {user.linked_in_url}: {e}")
    users_collection.update_one(
        {"email": user.email},  # Search by email
        {"$set": {
            "linked_in": user.linked_in_url,
            "linked_in_data": linked_in_data
        }},
        upsert=True  # Insert if not exists
    )
    return {"message":"successfully data stored"}
