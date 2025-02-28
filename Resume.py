import json

from decouple import config
from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
import openai
from pymongo import MongoClient

router = APIRouter(prefix="/router", tags=["Router"])

# MongoDB connection setup
client = MongoClient(config("MONGO_URI"))
db = client["auth_db"]
collection = db["users"]

# Initialize OpenAI client properly
openai_client = openai.OpenAI(api_key=config("OPENAI_API_KEY"))

class InputData(BaseModel):
    text: str

@router.post("/extract-data/{email_id}")
def extract_data(input_data: InputData, email_id: str):
    prompt = f"""
    Extract the following details from the given text and return the result as a valid JSON object without any extra text.

    Expected JSON format:
    {{
      "name": "Full Name",
      "bio": "Brief bio",
      "email": "Email address",
      "mobile_number": "Mobile number",
      "experience": [
        {{
          "job_title": "Title",
          "company": "Company",
          "years": "Number of years"
        }}
      ],
      "education": [
        {{
          "degree": "Degree",
          "institution": "University/College",
          "year": "Year of graduation"
        }}
      ],
      "certificates": [
        {{
          "title": "Certificate Name",
          "issuer": "Issuing Organization",
          "year": "Year of Issue"
        }}
      ]
    }}

    Text:
    {input_data.text}

    Strictly return only a valid JSON object. Do not include any additional text.
    """

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert data extractor."},
                {"role": "user", "content": prompt}
            ]
        )

        extracted_data = json.loads(response.choices[0].message.content)  # Direct JSON parsing

        # Update data in MongoDB
        collection.update_one(
            {"email": email_id},
            {"$set": {"text": input_data.text, "extracted_data": extracted_data}},
            upsert=True
        )

        return {"extracted_data": extracted_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
