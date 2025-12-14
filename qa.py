import os
import sqlite3
from openai import OpenAI
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")
DB_PATH = os.path.join(DATA_DIR, "metadata.db")


def save_chat_message(query, answer, sources=None):
    """Save a chat exchange to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    sources_str = ", ".join(sources) if sources else None
    cursor.execute(
        'INSERT INTO chat_history (query, answer, sources) VALUES (?, ?, ?)',
        (query, answer, sources_str)
    )
    conn.commit()
    conn.close()


def get_recent_history(limit=3):
    """Retrieve the most recent chat exchanges from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT query, answer FROM chat_history ORDER BY created_at DESC LIMIT ?',
        (limit,)
    )
    rows = cursor.fetchall()
    conn.close()
    # Return in chronological order (oldest first)
    return list(reversed(rows))


def clear_chat_history():
    """Clear all chat history from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_history')
    conn.commit()
    conn.close()

def get_qa_chain():
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        return None

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    if not os.path.exists(FAISS_INDEX_PATH):
        return None

    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    except:
        return None

    # Return vectorstore retriever instead of chain
    return vectorstore.as_retriever(search_kwargs={"k": 3})

def ask_question(query, selected_docs=None):
    retriever = get_qa_chain()
    if not retriever:
        return "Please upload documents first.", []
    
    try:
        # Get GitHub token
        api_key = os.getenv("GITHUB_TOKEN")
        if not api_key:
            return "GITHUB_TOKEN missing. Please add it to your .env file.", []
        
        # Initialize GitHub Models client (OpenAI-compatible)
        client = OpenAI(
            base_url="https://models.inference.ai.azure.com",
            api_key=api_key
        )
        
        # Retrieve relevant documents
        docs = retriever.invoke(query)
        
        # Filter by selected documents if provided
        if selected_docs and len(selected_docs) > 0:
            docs = [doc for doc in docs 
                   if os.path.basename(doc.metadata.get('source', '')) in selected_docs]
        
        # Build context from documents
        context = "\n\n".join([doc.page_content for doc in docs])
        
        # Add chat history context from database
        history_context = ""
        recent_history = get_recent_history(limit=3)
        if recent_history:
            history_context = "Previous conversation:\n" + "\n".join([f"Q: {q}\nA: {a}" for q, a in recent_history]) + "\n\n"
        
        # Create prompt
        full_prompt = f"""{history_context}Context from documents:
{context}

Current question: {query}

Please answer based on the provided context. If the answer isn't in the context, say so."""
        
        # Call GitHub Models GPT-4o mini
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful study assistant. Answer questions based on the provided document context."},
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.3
        )
        
        answer = response.choices[0].message.content
        
        # Format citations
        formatted_sources = []
        for doc in docs:
            page = doc.metadata.get('page', 0) + 1  # 0-indexed
            source = os.path.basename(doc.metadata.get('source', 'Unknown'))
            formatted_sources.append(f"{source} (Page {page})")
            
        unique_sources = list(set(formatted_sources))
        
        # Store in database
        save_chat_message(query, answer, unique_sources)
        
        return answer, unique_sources
    except Exception as e:
        return f"Error: {str(e)}", []

def clear_memory():
    """Clear all chat history from the database."""
    clear_chat_history()
