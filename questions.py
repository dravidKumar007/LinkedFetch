import openai
import json
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

# OpenAI API Key
openai.api_key = OPENAI_API_KEY

# FastAPI Router
router = APIRouter(prefix="/assessment", tags=["Assessment"])


def generate_questions(prompt: str):
    """Generates a set of questions dynamically using OpenAI"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )

        # Print raw response before parsing
        raw_content = response.choices[0].message.content.strip()
        print("Raw OpenAI Response:\n", raw_content)

        # Ensure response is valid JSON
        questions_json = json.loads(raw_content)  # Parse JSON
        return questions_json if isinstance(questions_json, list) else []
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail=f"Invalid JSON format from OpenAI: {raw_content}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI Error: {str(e)}")


@router.post("/start")
def start_test(email_id: str, job_role: str):
    """Start the test and provide the first psychometric question with options."""
   psychometric_prompt = """Generate 10 multiple-choice psychometric questions based on the 16PF (Sixteen Personality Factor Questionnaire). 

### Requirements:
1. Each question should assess a different personality trait from the 16PF model (e.g., extraversion, anxiety, independence, conscientiousness).
2. Questions should be neutral, clear, and relevant to personality assessment.
3. Each question must have exactly 4 answer choices labeled A, B, C, and D.
4. The answer choices should follow a **Likert scale format**:  
   - A. Strongly Agree  
   - B. Agree  
   - C. Disagree  
   - D. Strongly Disagree  

### Output Format:
Return the questions as a valid JSON list:
```json
[
  {
    "question": "Do you enjoy social interactions and large gatherings?",
    "options": [
      "A. Strongly Agree",
      "B. Agree",
      "C. Disagree",
      "D. Strongly Disagree"
    ]
  },
  {
    "question": "You prefer structured routines over spontaneous activities.",
    "options": [
      "A. Strongly Agree",
      "B. Agree",
      "C. Disagree",
      "D. Strongly Disagree"
    ]
  }
]
"""

    questions = generate_questions(psychometric_prompt)

    if not questions or len(questions) < 10:
        raise HTTPException(status_code=500, detail="Failed to generate psychometric questions.")

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
        "question": questions[0]["question"],
        "options": questions[0]["options"]
    }

@router.post("/answer")
def submit_answer(email_id: str, answer: str):
    """Receive an answer and send the next psychometric question."""
    user_data = responses_collection.find_one({"email_id": email_id})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found or test not started.")

    question_index = user_data["current_question_index"]
    user_data["psychometric_answers"].append(answer)

    if question_index < 9:
        next_question = user_data["psychometric_questions"][question_index + 1]
        responses_collection.update_one(
            {"email_id": email_id},
            {"$set": {"psychometric_answers": user_data["psychometric_answers"],
                      "current_question_index": question_index + 1}}
        )
        return {"message": "Next question", "question_number": question_index + 2,
                "question": next_question["question"], "options": next_question["options"]}
    ans_formate='{"question": "Question text"}'
    job_prompt = f"""
        Generate 5 interview questions for a {user_data["job_role"]} role.
        The questions should be open-ended (not MCQ) and assess technical knowledge and problem-solving skills.
        Return questions in JSON format: {ans_formate}
        """

    job_questions = generate_questions(job_prompt)

    if not job_questions or len(job_questions) < 5:
        raise HTTPException(status_code=500, detail="Failed to generate job-specific questions.")

    formatted_job_questions = [{"question": q} for q in job_questions]
    responses_collection.update_one(
        {"email_id": email_id},
        {"$set": {"job_role_questions": formatted_job_questions, "job_role_answers": [],
                  "current_job_question_index": 0}}
    )

    return {"message": "Psychometric test completed. Starting job-role-specific questions.", "question_number": 1,
            "question": formatted_job_questions[0]["question"]}



@router.post("/job-answer")
def submit_job_answer(email_id: str, answer: str):
    """Receive job-role answer and send the next question or generate final analysis."""
    user_data = responses_collection.find_one({"email_id": email_id})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found or test not started.")

    job_question_index = user_data["current_job_question_index"]
    responses_collection.update_one(
        {"email_id": email_id},
        {"$push": {"job_role_answers": answer}, "$inc": {"current_job_question_index": 1}}
    )

    # If more questions remain, return the next one
    if job_question_index < 4:
        next_question = user_data["job_role_questions"][job_question_index + 1]
        return {
            "message": "Next question",
            "question_number": job_question_index + 2,
            "question": next_question["question"]
        }

    # Preparing structured analysis prompt
    analysis_prompt = f"""
        Analyze the following assessment data and generate structured insights in valid JSON format.

        ### Psychometric Questions and Answers:
        {json.dumps(user_data["psychometric_questions"], indent=2)}

        ### Psychometric Answers:
        {json.dumps(user_data["psychometric_answers"], indent=2)}

        ### Job Role-Specific Questions and Answers:
        {json.dumps(user_data["job_role_questions"], indent=2)}

        ### Job Role-Specific Answers:
        {json.dumps(user_data["job_role_answers"], indent=2)}

        ### Important Instructions:
        - Return ONLY a valid JSON object—do NOT include extra text, explanations, or formatting.
        - Ensure the output strictly follows this JSON structure:
        {{
            "overall_score": "XX%",
            "top_skills": [
                {{"skill": "Skill Name", "percentage": "XX%"}},
                {{"skill": "Skill Name", "percentage": "XX%"}},
                {{"skill": "Skill Name", "percentage": "XX%"}}
            ],
            "personality_traits": [
                {{"trait": "Trait Name", "percentage": "XX%"}},
                {{"trait": "Trait Name", "percentage": "XX%"}},
                {{"trait": "Trait Name", "percentage": "XX%"}}
            ],
            "areas_of_improvement": [
                {{"area": "Improvement Area", "percentage": "XX%"}},
                {{"area": "Improvement Area", "percentage": "XX%"}},
                {{"area": "Improvement Area", "percentage": "XX%"}}
            ]
        }}
        - Ensure each section contains exactly three items.
        - Percentages should be in "XX%" format based on logical inference from the data provided.
        - DO NOT generate placeholder values—derive insights based on user answers.
    """

    print("Analysis Prompt:", analysis_prompt)  # Debugging

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": analysis_prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        raw_content = response.choices[0].message.content.strip()
        print("Raw OpenAI Response:", raw_content)

        # Parse response into JSON
        analysis_dict = json.loads(raw_content)
        if not isinstance(analysis_dict, dict):
            raise ValueError("Invalid JSON format")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"Invalid OpenAI response: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")

    # Store final analysis
    responses_collection.update_one({"email_id": email_id}, {"$set": {"final_analysis": analysis_dict, "test_completed": True}})

    return {"message": "Assessment Complete", "analysis": analysis_dict}
