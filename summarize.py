import os
from groq import Groq
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()
DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")

def get_summary(style="Bulleted"):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return "GROQ_API_KEY missing. Please add it to your .env file."
    
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not os.path.exists(FAISS_INDEX_PATH): return "No docs found."
    
    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 15})  # Increased from 10 to 15
        docs = retriever.invoke("core concepts summary main ideas key points details conclusion")
        context_text = "\n".join([d.page_content for d in docs])
    except Exception as e:
        return f"Error: {e}"

    # Initialize Groq client
    client = Groq(api_key=api_key)
    
    style_prompt = {
        "Bulleted": "a comprehensive bulleted list with detailed key takeaways, including important details and examples. Each bullet point should be informative and well-explained.",
        "Paragraph": "a detailed narrative summary with multiple paragraphs that thoroughly covers the main topics, supporting details, and key insights",
        "ELI5": "a detailed but simple explanation that a 5-year-old could understand, with examples and step-by-step breakdowns"
    }

    prompt = f"""
    Create a COMPREHENSIVE, MEDIUM-LENGTH summary of the following text as {style_prompt.get(style, "a detailed summary")}.
    
    Requirements:
    - Be thorough and detailed
    - Include important specifics, not just high-level points
    - Cover all major topics and subtopics
    - Provide context and explanations
    - Minimum 300-500 words
    
    Text:
    {context_text[:18000]}
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000  # Increased token limit for longer summaries
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Summary failed: {e}"
