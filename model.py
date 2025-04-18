from pydantic import BaseModel
from typing import List, Dict

class QuizParams(BaseModel):
    description: str
    difficulty: str
    num_questions: int

class GeneratedQuestion(BaseModel):
    question: str
    options: List[str]
    

class GeneratedQuizResponse(BaseModel):
    quiz_id: str
    questions: List[GeneratedQuestion]
    correct_answers: List[str]
    explanations: List[str]
    
class SubmitAnswerRequest(BaseModel):
    quiz_id: str
    user_answers: List[str]  # List of selected options

class ScoreResponse(BaseModel):
    score: int
    total_questions: int

class CorrectAnswersResponse(BaseModel):
    correct_answers: List[str]
    explanations: List[str]


