import os
import json
from groq import Groq
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")

def generate_quiz(selected_docs=None, num_questions=10, difficulty="medium"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"questions": [], "error": "GROQ_API_KEY missing. Please add it to your .env file."}

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    if not os.path.exists(FAISS_INDEX_PATH):
        return {"questions": [], "error": "No knowledge base found."}

    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        
        # Get more documents if filtering
        search_k = 20 if selected_docs else 8
        retriever = vectorstore.as_retriever(search_kwargs={"k": search_k}) 
        docs = retriever.invoke("important concepts summary definitions main points")
        
        print(f"\n=== QUIZ GENERATION DEBUG ===")
        print(f"Selected documents: {selected_docs}")
        print(f"Num questions requested: {num_questions}")
        print(f"Difficulty: {difficulty}")
        print(f"Retrieved {len(docs)} documents from FAISS")
        
        # Filter by selected documents if provided
        if selected_docs and len(selected_docs) > 0:
            filtered_docs = []
            for doc in docs:
                doc_source = doc.metadata.get('source', '')
                doc_filename = os.path.basename(doc_source)
                if doc_filename in selected_docs:
                    filtered_docs.append(doc)
            
            print(f"Filtered to {len(filtered_docs)} documents from selected files")
            docs = filtered_docs if filtered_docs else docs
        
        if not docs:
            return {"questions": [], "error": "No content found in selected documents."}
        
        context_text = "\n\n".join([d.page_content for d in docs])
        print(f"Context length: {len(context_text)} characters")
        print(f"=== END DEBUG ===\n")
        
    except Exception as e:
        return {"questions": [], "error": f"Error retrieving context: {str(e)}"}

    # Initialize Groq client
    client = Groq(api_key=api_key)

    # Build document context info
    doc_names = list(set([os.path.basename(d.metadata.get('source', 'Unknown')) for d in docs]))
    doc_context = f"Content from documents: {', '.join(doc_names)}" if doc_names else ""

    prompt = f"""
    Based on the following text from study materials:
    {context_text[:12000]}
    
    {doc_context}

    Generate exactly {num_questions} UNIQUE Multiple Choice Questions.
    Difficulty level: {difficulty}
    
    IMPORTANT RULES:
    1. Each question MUST cover a DIFFERENT topic or concept
    2. NO duplicate or similar questions
    3. Questions should span the ENTIRE content provided
    4. Include questions from ALL documents if multiple are provided
    5. Vary question types: definitions, applications, comparisons, examples
    
    Return strictly a JSON array with this structure:
    [
      {{
        "question": "question text",
        "options": ["option A", "option B", "option C", "option D"],
        "correct": 0
      }}
    ]
    
    The "correct" field should be the index (0-3) of the correct answer.
    Difficulty guidelines:
    - Easy: Basic recall and simple definitions
    - Medium: Understanding and application of concepts
    - Hard: Analysis, comparison, and complex scenarios
    
    Generate EXACTLY {num_questions} unique questions. No markdown formatting. Raw JSON only.
    """

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
            
        questions = json.loads(content.strip())
        return {"questions": questions}
    except Exception as e:
        return {"questions": [], "error": f"Quiz generation failed: {str(e)}"}
