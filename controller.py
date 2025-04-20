from fastapi import FastAPI, HTTPException
from typing import Dict
from fastapi.middleware.cors import CORSMiddleware
from model import QuizParams, GeneratedQuizResponse, SubmitAnswerRequest, ScoreResponse, CorrectAnswersResponse
from mangum import Mangum
import uuid
import boto3

app = FastAPI()
session = boto3.Session()
bedrock = boto3.client(service_name='bedrock-runtime', region_name = "us-east-1" )
modelId="anthropic.claude-3-5-sonnet-20240620-v1:0"
handler = Mangum(app)

# handle CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
    expose_headers=["*"],  # Expose all headers
)

# In-memory storage for generated quizzes (for simplicity)
quiz_storage: Dict[str, Dict] = {}

quiz_generation_tool = {
    "toolSpec": {
        "name": "generate_quiz_data",
        "description": "Generate multiple-choice quiz questions with options and correct answers.",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question_text": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4},
                                "correct_answer": {"type": "string", "enum": ["A", "B", "C", "D"]},
                                "explanation": {"type": "string"}
                            },
                            "required": ["question_text", "options", "correct_answer"]
                        },
                        "minItems": 1
                    }
                },
                "required": ["questions"]
            }
        }
    }
}

def generate_quiz_with_tool_calling(params: QuizParams):
    system_prompt = f"""Generate {params.num_questions} multiple-choice questions about {params.description} with a difficulty level of {params.difficulty}. Each question should have exactly 4 options. Please use the 'generate_quiz_data' tool to format the output.
    You are a quizbot that provides multiple-choice questions, answers, and explanations to users based on the context provided. The goal is to help users understand the concepts by presenting questions of varying difficulty levels.

Guidelines:
The questions should be relevant to the context and test the user's understanding of the material.
Difficulty Levels:

Level 1 (Very Easy): The question should be straightforward and simple, with easy options. The explanation should be very simplified, focusing on the basic concept.

Level 2 (Easy): The question should be easy but implicit, requiring a bit more thought to answer. The options should also be easy but slightly more nuanced. The explanation should be more complex and go a bit deeper into the concept.

Level 3 (Medium): The question should require some understanding of the topic and be more implicit in nature. The options should provide close alternatives. The explanation should involve practical application or deeper insights into the topic.

Level 4 (Hard): The question should be challenging, requiring a strong understanding of the topic. The options should be distinct but tricky. The explanation should go into detail, possibly covering edge cases or advanced concepts.

Level 5 (Very Hard): The question should be highly complex, possibly involving advanced techniques, theory, or application. The options should be sophisticated and require careful thought. The explanation should dive into advanced concepts, assumptions, and practical considerations.

Output Format:
You must use the tool "generate_quiz_questions" to return your response. 
The tool requires a list of questions, where each question is a dictionary containing:
•⁠  ⁠"question": The question text
•⁠  ⁠"options": A list of 4 options labeled as strings "A", "B", "C", and "D" (not including the letter labels in the option text)
•⁠  ⁠"answer": The correct option letter ("A", "B", "C", or "D")
•⁠  ⁠"explanation": A brief explanation of why the answer is correct

All explanations should be clear and concise, helping the user understand the concept better, not more than a sentence or two
    
"""
    try:
        message = {
                "role": "user",
                "content": [
                    { "text": f"<context>{QuizParams}</context> \n. Please use the right tool to generate the Quiz JSON based on the context." },
                    {"text": f"Generate {params.num_questions} multiple-choice questions about {params.description} with a difficulty level of {params.difficulty}. Each question should have exactly 4 options. Please use the 'generate_quiz_data' tool to format the output."}
                ],
            }
        response = bedrock.converse(
            modelId=modelId,
            messages=[message],
            system=[
                { "text": system_prompt}
            ],
        inferenceConfig={
                "maxTokens": 2000,
                "temperature": 0
            },
            toolConfig={
                "tools": [quiz_generation_tool]
            }
        )
        response_body = response['output']['message']
        print(response_body)

        tool_calls = response_body.get('tool_calls')

        tool_use = response_body.get('content', [])[1].get('toolUse') if len(response_body.get('content', [])) > 1 else None

        if tool_use and tool_use.get('name') == "generate_quiz_data":
            arguments = tool_use.get('input')
            if arguments and arguments.get('questions'):
                generated_questions_data = arguments.get('questions')
                if len(generated_questions_data) == params.num_questions:
                    quiz_id = str(uuid.uuid4())
                    questions = [{"question": q['question_text'], "options": q['options']} for q in generated_questions_data]
                    correct_answers = [q['correct_answer'] for q in generated_questions_data]
                    explanations = [q['explanation'] for q in generated_questions_data]
                    quiz_storage[quiz_id] = {"questions_data": generated_questions_data, "correct_answers": correct_answers, "explanations": explanations}
                    return {"quiz_id": quiz_id, "questions": questions, "correct_answers": correct_answers, "explanations": explanations}
                else:
                    raise HTTPException(status_code=500, detail="Generated number of questions does not match the request.")
            else:
                raise HTTPException(status_code=500, detail="No 'questions' found in the tool call arguments.")
        else:
            raise HTTPException(status_code=500, detail="No valid tool call found in the response.")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate_quiz/", response_model=GeneratedQuizResponse)
async def generate_quiz_endpoint(params: QuizParams):
    return generate_quiz_with_tool_calling(params)

@app.post("/submit_quiz/", response_model=ScoreResponse)
async def submit_quiz(request: SubmitAnswerRequest):
    quiz_data = quiz_storage.get(request.quiz_id)
    if not quiz_data:
        raise HTTPException(status_code=404, detail="Quiz not found")

    correct_answers = quiz_data["correct_answers"]
    print(correct_answers)
    user_answers = request.user_answers
    print(user_answers)

    if len(user_answers) != len(correct_answers):
        raise HTTPException(status_code=400, detail="Number of answers does not match the number of questions.")

    score = 0
    for i in range(len(correct_answers)):
        user_answer_raw = user_answers[i]
        # We need to find the correct answer within the options for comparison
        user_answer = user_answer_raw.split('. ', 1)[0] if user_answer_raw and '. ' in user_answer_raw else user_answer_raw
        print(user_answer)
        correct_answer_from_data = quiz_data["questions_data"][i]["correct_answer"]
        if i < len(user_answers) and user_answer.strip().lower() == correct_answer_from_data.strip().lower():
            score += 1

    return {"score": score, "total_questions": len(correct_answers)}

@app.get("/get_answers/{quiz_id}", response_model=CorrectAnswersResponse)
async def get_answers(quiz_id: str):
    quiz_data = quiz_storage.get(quiz_id)
    if not quiz_data:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return {"correct_answers": quiz_data["correct_answers"], "explanations": quiz_data["explanations"]}
