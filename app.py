import streamlit as st
import string
import requests
from streamlit_router import StreamlitRouter

backend_url = "http://127.0.0.1:8000"

# Initialize router
router = StreamlitRouter()

# Initialize session state (if not already done)
if 'quiz_id' not in st.session_state:
    st.session_state['quiz_id'] = None
if 'questions' not in st.session_state:
    st.session_state['questions'] = None
if 'user_answers' not in st.session_state:
    st.session_state['user_answers'] = None
if 'show_answers' not in st.session_state:
    st.session_state['show_answers'] = False
if 'score' not in st.session_state:
    st.session_state['score'] = None
if 'correct_answers' not in st.session_state:
    st.session_state['correct_answers'] = None
if 'explanations' not in st.session_state:
    st.session_state['explanations'] = None
if 'quiz_description' not in st.session_state:
    st.session_state['quiz_description'] = ""
if 'difficulty_level' not in st.session_state:
    st.session_state['difficulty_level'] = "Easy"
if 'num_questions' not in st.session_state:
    st.session_state['num_questions'] = 5

def generate_quiz_page(router):
    st.title("Quizly 📚")
    st.session_state['quiz_description'] = st.text_input("Enter the topic for the quiz:", key="quiz_description_input")
    st.session_state['difficulty_level'] = st.selectbox("Select difficulty level:", ["Easy", "Medium", "Hard", "Very Hard"], key="difficulty_select")
    st.session_state['num_questions'] = st.number_input("Number of questions:", min_value=1, max_value=10, value=st.session_state['num_questions'], step=1, key="num_questions_input")
    if st.button("Generate Quiz"):
        if st.session_state['quiz_description']:
            try:
                with st.spinner("Generating quiz..."):
                    response = requests.post(f"{backend_url}/generate_quiz/", json={
                        "description": st.session_state['quiz_description'],
                        "difficulty": st.session_state['difficulty_level'],
                        "num_questions": st.session_state['num_questions']
                    })
                    response.raise_for_status()
                    quiz_data = response.json()
                    st.session_state['quiz_id'] = quiz_data['quiz_id']
                    st.session_state['questions'] = quiz_data['questions']
                    st.session_state['user_answers'] = [""] * len(st.session_state['questions'])
                    st.session_state['show_answers'] = False
                    st.session_state['score'] = None
                    st.session_state['correct_answers'] = None
                st.success("Quiz generated successfully! Proceed to answer the questions.")
                router.redirect(*router.build("quiz_page"))  # 👈 this line triggers the page change
            except requests.exceptions.RequestException as e:
                st.error(f"Error generating quiz: {e}")
        else:
            st.warning("Please enter a quiz topic.")
def quiz_page(router):
    if st.session_state['questions']:
        st.subheader("Quiz Questions:")
        for i, question_item in enumerate(st.session_state['questions']):
            question = question_item['question']
            options = question_item['options']
            labeled_options = [f"{letter}. {option}" for letter, option in zip(string.ascii_uppercase, options)]
            st.write(f"**{question}**")
            st.session_state['user_answers'][i] = st.radio(f"Select your answer for question {i+1}", labeled_options, index= None, key=f"q_{i}")

        if st.button("Submit Answers"):
            try:
                response = requests.post(f"{backend_url}/submit_quiz/", json={
                    "quiz_id": st.session_state['quiz_id'],
                    "user_answers": st.session_state['user_answers']
                })
                response.raise_for_status()
                result = response.json()
                st.session_state['score'] = result['score']
                st.session_state['total_questions'] = result['total_questions']
                st.success(f"Your score: {st.session_state['score']} / {st.session_state['total_questions']}")
            except requests.exceptions.RequestException as e:
                st.error(f"Error submitting answers: {e}")

        if st.session_state.get('score') is not None and st.button("Show Correct Answers"):
            try:
                response = requests.get(f"{backend_url}/get_answers/{st.session_state['quiz_id']}")
                response.raise_for_status()
                answers_data = response.json()
                print(answers_data)
                st.session_state['correct_answers'] = answers_data['correct_answers']
                st.session_state['explanations'] = answers_data['explanations']
                st.session_state['show_answers'] = True
            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching correct answers: {e}")

        if st.session_state.get('show_answers'):
            st.subheader("Correct Answers & Explanations:")
            if 'questions' in st.session_state and 'correct_answers' in st.session_state and 'explanations' in st.session_state:
                for i, question_item in enumerate(st.session_state['questions']):
                    question = question_item['question']
                    correct_answer = st.session_state['correct_answers'][i]
                    explanation = st.session_state['explanations'][i]
                    user_answer = st.session_state['user_answers'][i]

                    st.markdown(f"### Question {i+1}")
                    st.markdown(f"**{question}**")

                    if user_answer.split('.')[0].strip() == correct_answer:
                        st.success(f"✅ You answered correctly: {user_answer.split('.')[0].strip() if user_answer else 'None'}")
                    else:
                        st.error(f"❌ Your answer: {user_answer.split('.')[0].strip() if user_answer else 'None'}")
                        st.success(f"✅ Correct Answer: {correct_answer}")

                    st.info(f"🧠 Explanation: {explanation}")
                    st.divider()


        if st.button("Generate New Quiz"):
            st.session_state['quiz_id'] = None
            st.session_state['questions'] = None
            st.session_state['user_answers'] = None
            st.session_state['show_answers'] = False
            st.session_state['score'] = None
            st.session_state['correct_answers'] = None
            st.session_state['explanations'] = None
            router.redirect(*router.build("generate_quiz_page")) # Navigate back to the generate page
    else:
        st.write("No quiz questions available. Please generate a quiz first.")
        if st.button("Back to Quiz Generation"):
            router.register(generate_quiz_page, "/", methods=["GET"])

# Define routes
router.register(generate_quiz_page, '/')
router.register(quiz_page, '/quiz')

# Serve the router
router.serve()