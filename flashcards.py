import os
import json
import sqlite3
from datetime import datetime, date
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
import srs_algorithm

load_dotenv()
DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")
DB_PATH = os.path.join(DATA_DIR, "metadata.db")


class FlashcardManager:
    """Manages flashcard database operations and SRS scheduling"""
    
    @staticmethod
    def save_flashcard(front, back, source_document=None, deck_name="Default"):
        """
        Save a flashcard to the database with initial SRS state.
        
        Args:
            front (str): Question/term on front of card
            back (str): Answer/definition on back of card
            source_document (str): Optional source document filename
            deck_name (str): Deck name for organization
        
        Returns:
            int: ID of the inserted flashcard
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        initial_state = srs_algorithm.get_initial_state()
        
        cursor.execute('''
            INSERT INTO flashcards 
            (front, back, source_document, deck_name, easiness_factor, repetition_count, interval_days, next_review_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            front, back, source_document, deck_name,
            initial_state['easiness_factor'],
            initial_state['repetition_count'],
            initial_state['interval_days'],
            initial_state['next_review_date']
        ))
        
        flashcard_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return flashcard_id
    
    @staticmethod
    def get_due_flashcards():
        """
        Get all flashcards that are due for review today.
        
        Returns:
            list: List of flashcard dictionaries
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        
        cursor.execute('''
            SELECT * FROM flashcards 
            WHERE next_review_date <= ?
            ORDER BY next_review_date ASC
        ''', (today,))
        
        rows = cursor.fetchall()
        flashcards = [dict(row) for row in rows]
        
        conn.close()
        return flashcards
    
    @staticmethod
    def submit_review(flashcard_id, quality):
        """
        Submit a review for a flashcard and update its SRS scheduling.
        
        Args:
            flashcard_id (int): ID of the flashcard being reviewed
            quality (int or str): Quality rating (0-5 or button name)
        
        Returns:
            dict: Updated flashcard state
        """
        # Convert button names to quality ratings if needed
        if isinstance(quality, str):
            quality = srs_algorithm.simplified_quality_map(quality)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current flashcard state
        cursor.execute('''
            SELECT easiness_factor, repetition_count, interval_days 
            FROM flashcards WHERE id = ?
        ''', (flashcard_id,))
        
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        
        ef, rep_count, interval = row
        
        # Calculate new state using SM-2 algorithm
        new_state = srs_algorithm.calculate_next_review(
            quality, ef, rep_count, interval
        )
        
        # Update flashcard
        cursor.execute('''
            UPDATE flashcards 
            SET easiness_factor = ?,
                repetition_count = ?,
                interval_days = ?,
                next_review_date = ?
            WHERE id = ?
        ''', (
            new_state['easiness_factor'],
            new_state['repetition_count'],
            new_state['interval_days'],
            new_state['next_review_date'],
            flashcard_id
        ))
        
        # Record the review
        cursor.execute('''
            INSERT INTO reviews (flashcard_id, quality_rating)
            VALUES (?, ?)
        ''', (flashcard_id, quality))
        
        conn.commit()
        conn.close()
        
        return new_state
    
    @staticmethod
    def get_statistics():
        """
        Get learning statistics.
        
        Returns:
            dict: Statistics including total cards, due cards, and review count
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        today = date.today().isoformat()
        
        # Total flashcards
        cursor.execute('SELECT COUNT(*) FROM flashcards')
        total_cards = cursor.fetchone()[0]
        
        # Due flashcards
        cursor.execute('SELECT COUNT(*) FROM flashcards WHERE next_review_date <= ?', (today,))
        due_cards = cursor.fetchone()[0]
        
        # Total reviews
        cursor.execute('SELECT COUNT(*) FROM reviews')
        total_reviews = cursor.fetchone()[0]
        
        # Reviews today
        cursor.execute('''
            SELECT COUNT(*) FROM reviews 
            WHERE DATE(reviewed_at) = DATE('now')
        ''')
        reviews_today = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_cards': total_cards,
            'due_cards': due_cards,
            'total_reviews': total_reviews,
            'reviews_today': reviews_today
        }
    
    @staticmethod
    def get_all_flashcards():
        """
        Get all flashcards (for browsing/management).
        
        Returns:
            list: List of all flashcard dictionaries
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM flashcards ORDER BY created_at DESC')
        rows = cursor.fetchall()
        flashcards = [dict(row) for row in rows]
        
        conn.close()
        return flashcards
    
    @staticmethod
    def delete_flashcard(flashcard_id):
        """
        Delete a flashcard and its associated reviews.
        
        Args:
            flashcard_id (int): ID of flashcard to delete
        
        Returns:
            bool: True if deleted successfully
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM flashcards WHERE id = ?', (flashcard_id,))
        
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        
        return deleted
    
    @staticmethod
    def delete_all_flashcards():
        """
        Delete all flashcards and their associated reviews.
        
        Returns:
            int: Number of flashcards deleted
        """
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Delete all reviews first (they reference flashcards)
        cursor.execute('DELETE FROM reviews')
        
        # Delete all flashcards
        cursor.execute('DELETE FROM flashcards')
        deleted_count = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return deleted_count


def generate_flashcards():
    """Generate flashcards from document content using Groq AI"""
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        return {"flashcards": [], "error": "GITHUB_TOKEN missing. Please add it to your .env file."}
    
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    if not os.path.exists(FAISS_INDEX_PATH):
        return {"flashcards": [], "error": "No documents found."}
    
    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
        docs = retriever.invoke("key concepts definitions important terms explanations")
        context_text = "\n\n".join([d.page_content for d in docs])
        
    except Exception as e:
        return {"flashcards": [], "error": f"Error: {str(e)}"}
    
    # Initialize GitHub Models client (OpenAI-compatible)
    from openai import OpenAI
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=api_key
    )
    
    prompt = f"""
    Based on the following text, create 10 flashcards for studying.
    Return strictly a JSON array with this structure:
    [
      {{
        "front": "Question or term",
        "back": "Answer or definition"
      }}
    ]
    
    Each flashcard should test understanding of key concepts.
    No markdown formatting. Raw JSON only.
    
    Text:
    {context_text[:10000]}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful study assistant. Create clear, concise flashcards."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        
        flashcards = json.loads(content.strip())
        return {"flashcards": flashcards}
        
    except Exception as e:
        return {"flashcards": [], "error": f"Flashcard generation failed: {str(e)}"}
