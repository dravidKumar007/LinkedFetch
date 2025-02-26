import openai
from fastapi import FastAPI, HTTPException, APIRouter
from pymongo import MongoClient
from decouple import config

# Load environment variables
OPENAI_API_KEY = config("OPENAI_API_KEY")
MONGO_URI = config("MONGO_URI")

# MongoDB Connection
client = MongoClient(MONGO_URI)
db = client["job_assessment"]
responses_collection = db["responses"]

# FastAPI router
openai.api_key = OPENAI_API_KEY

router = APIRouter(prefix="/assessment", tags=["Assessment"])


def generate_questions(prompt: str):
    """Generates a set of questions dynamically using OpenAI"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content.strip().split("\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI Error: {str(e)}")


@router.post("/start")
def start_test(email_id: str, job_role: str):
    """Start test and send the first psychometric question."""
    psychometric_prompt = """
    Generate 7 psychometric questions that assess a candidate's personality and workplace behavior.
    Questions should be diverse and relevant to professional settings.
    Provide one question per line.
    """
    questions = generate_questions(psychometric_prompt)

    if not questions or len(questions) < 7:
        raise HTTPException(status_code=500, detail="Failed to generate psychometric questions.")

    # Save questions in MongoDB
    responses_collection.insert_one({
        "email_id": email_id,
        "job_role": job_role,
        "psychometric_questions": questions,
        "psychometric_answers": [],
        "current_question_index": 0
    })

    return {
        "message": "Test started",
        "question_number": 1,
        "question": questions[0]
    }


@router.post("/answer")
def submit_answer(email_id: str, answer: str):
    """Receive an answer and send the next psychometric question."""
    user_data = responses_collection.find_one({"email_id": email_id})

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found or test not started.")

    # Store the answer
    question_index = user_data["current_question_index"]
    user_data["psychometric_answers"].append(answer)

    # If there are more questions, send the next one
    if question_index < 6:
        next_question = user_data["psychometric_questions"][question_index + 1]
        responses_collection.update_one(
            {"email_id": email_id},
            {"$set": {"psychometric_answers": user_data["psychometric_answers"],
                      "current_question_index": question_index + 1}}
        )
        return {
            "message": "Next question",
            "question_number": question_index + 2,
            "question": next_question
        }

    # If psychometric questions are done, start job-specific questions
    job_prompt = f"""
    Generate 5 job role-specific interview questions for a {user_data["job_role"]}.
    These questions should assess technical skills, problem-solving, and domain knowledge.
    Provide one question per line.
    """
    job_questions = generate_questions(job_prompt)

    if not job_questions or len(job_questions) < 5:
        raise HTTPException(status_code=500, detail="Failed to generate job-specific questions.")

    responses_collection.update_one(
        {"email_id": email_id},
        {"$set": {
            "job_role_questions": job_questions,
            "job_role_answers": [],
            "current_job_question_index": 0
        }}
    )

    return {
        "message": "Psychometric test completed. Starting job-role-specific questions.",
        "question_number": 1,
        "question": job_questions[0]
    }


@router.post("/job-answer")
def submit_job_answer(email_id: str, answer: str):
    """Receive job-role answer, send the next question, and store the final analysis result."""
    user_data = responses_collection.find_one({"email_id": email_id})

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found or test not started.")

    # Store the job question answer
    job_question_index = user_data["current_job_question_index"]
    user_data["job_role_answers"].append(answer)

    # If there are more job questions, send the next one
    if job_question_index < 4:
        next_question = user_data["job_role_questions"][job_question_index + 1]

        responses_collection.update_one(
            {"email_id": email_id},
            {"$set": {
                "job_role_answers": user_data["job_role_answers"],
                "current_job_question_index": job_question_index + 1
            }}
        )

        return {
            "message": "Next question",
            "question_number": job_question_index + 2,
            "question": next_question
        }

    # If all questions are answered, analyze the results
    all_answers = user_data["psychometric_answers"] + user_data["job_role_answers"]

    analysis_prompt = f"""
    Analyze the following psychometric and job-related answers and determine:
    1. Top 3 skills with percentage.
    2. Top 3 personality traits with percentage.
    3. Top 3 areas of improvement with percentage.

    Answers: {all_answers}

    Response Format:
    Skills:
    1. Skill Name : Percentage
    2. Skill Name : Percentage
    3. Skill Name : Percentage

    Personality Traits:
    1. Trait Name : Percentage
    2. Trait Name : Percentage
    3. Trait Name : Percentage

    Areas of Improvement:
    1. Area Name : Percentage
    2. Area Name : Percentage
    3. Area Name : Percentage
    """

    analysis = generate_questions(analysis_prompt)

    # Store final analysis results in MongoDB
    responses_collection.update_one(
        {"email_id": email_id},
        {"$set": {"final_analysis": analysis, "test_completed": True}}
    )

    return {
        "message": "Assessment Complete",
        "analysis": analysis
    }

