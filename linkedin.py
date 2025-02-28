from urllib.parse import urlencode

import requests
from decouple import config

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import RedirectResponse
from mongo import users_collection
import  logging

router = APIRouter(prefix="/linkedin", tags=["linkedin"])

CLIENT_ID = config("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = config("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = "https://linkedfetch.onrender.com/linkedin/callback"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
PROFILE_URL = "https://api.linkedin.com/v2/userinfo"
EMAIL_URL = "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))"


class LinkedInLogin(BaseModel):
    email: str
    linked_in_url: str
def fetch_linked_in_data(linked_in_url: str):
    # Adjust API URL to accept the query parameter 'url'
    api_url = "https://nubela.co/proxycurl/api/v2/linkedin"  # Adjust API URL without embedding LinkedIn URL in path

    # Append the LinkedIn URL as a query parameter
    params = {"url": linked_in_url}

    headers = {
        "Authorization": "Bearer SCHyqcvtE_JyodZvD2-uag"  # Use the actual API key
    }

@router.get("/redirecturl")
def redirecturl():
     # Debug output
     auth_url = (
         "https://www.linkedin.com/oauth/v2/authorization"
         "?response_type=code"
         f"&client_id={CLIENT_ID}"
         f"&redirect_uri={REDIRECT_URI}"
         "&scope=+profile+email"
     )

     return RedirectResponse("https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id=86etlqmbc98tmt&redirect_uri=https%3A%2F%2Flinkedfetch.onrender.com%2Flinkedin%2Fcallback&scope=profile%20email%20openid")

@router.get("/callback")
def linkedin_callback(request: Request):
    """Handles LinkedIn OAuth callback and retrieves user info"""
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not found")

    # Exchange authorization code for access token
    token_response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    token_data = token_response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to retrieve access token")

    # Fetch user profile
    headers = {"Authorization": f"Bearer {access_token}"}
    profile_response = requests.get(PROFILE_URL, headers=headers)
    profile_data = profile_response.json()




    return RedirectResponse("https://xohack-2025-frontend.onrender.com/upload-details/"+profile_data['email'])
    


@router.get("/profile/{email}")
def fetch_linked_in_data(email: str):
    user = users_collection.find_one({"email": email})
    if user:
        if "linked_in_data" in user:
            return user["linked_in_data"]  # Return the LinkedIn data
        else:
            return {"error": "LinkedIn data not found"}
    return {"error": "User not found"}


@router.post("/linkedin_login")
def addLinkedIn(user:LinkedInLogin):
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
