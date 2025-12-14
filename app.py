from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json

# Import backend modules
import ingest
import ingest_helper
import qa
import quiz
import summarize
import flashcards
import mindmap
import tts

app = Flask(__name__, static_folder='static')
CORS(app)

# Serve the main page
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# API Endpoints
@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    import threading
    import sqlite3
    
    files = request.files.getlist('files')
    temp_files = []
    saved_files = []
    
    # Get existing files to check for duplicates
    db_path = os.path.join('data', 'metadata.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('SELECT filename FROM uploads')
    existing_files = set(row[0] for row in cursor.fetchall())
    
    # Save uploaded files to disk AND add to database immediately
    for file in files:
        if file.filename.endswith('.pdf'):
            # Skip if already exists
            if file.filename in existing_files:
                print(f"Skipping duplicate: {file.filename}")
                continue
                
            temp_path = os.path.join('data', 'temp', file.filename)
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            file.save(temp_path)
            
            # Add to database immediately so it appears in list
            cursor.execute('INSERT INTO uploads (filename) VALUES (?)', (file.filename,))
            saved_files.append(file.filename)
            existing_files.add(file.filename)
            
            # Create file-like object for background indexing
            class TempFile:
                def __init__(self, path):
                    self.name = path
            
            temp_files.append(TempFile(temp_path))
    
    conn.commit()
    conn.close()
    
    if not temp_files:
        return jsonify({'error': 'No valid PDF files provided (may be duplicates)'}), 400
    
    # Index files in background (non-blocking)
    def index_in_background():
        try:
            print(f"[Background] Starting indexing for {len(temp_files)} files...")
            # Just do the embedding/indexing part, database already updated
            result = ingest_helper.index_documents_only(temp_files)
            print(f"[Background] {result}")
        except Exception as e:
            print(f"[Background] Indexing error: {e}")
            import traceback
            traceback.print_exc()
    
    # Start background thread
    index_thread = threading.Thread(target=index_in_background, daemon=True)
    index_thread.start()
    
    # Return immediately
    return jsonify({
        'message': f'Uploaded {len(saved_files)} file(s). Indexing in background (~30-60s).',
        'files': saved_files,
        'note': 'Files will be searchable once indexing completes'
    })

@app.route('/api/documents', methods=['GET'])
def list_documents():
    docs = ingest.get_uploaded_documents()
    return jsonify({'documents': docs})

@app.route('/api/documents/<path:filename>', methods=['DELETE'])
def delete_document(filename):
    """Delete an uploaded document and rebuild FAISS index in background"""
    try:
        import sqlite3
        import threading
        
        # Delete file from disk
        file_path = os.path.join('data', 'temp', filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted file: {file_path}")
        
        # Delete from database
        db_path = os.path.join('data', 'metadata.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM uploads WHERE filename = ?', (filename,))
        conn.commit()
        conn.close()
        print(f"Removed from database: {filename}")
        
        # Rebuild FAISS index in background thread (non-blocking)
        def rebuild_in_background():
            try:
                print(f"[Background] Starting FAISS rebuild after deleting {filename}...")
                result = ingest.rebuild_faiss_index()
                print(f"[Background] {result}")
            except Exception as e:
                print(f"[Background] FAISS rebuild error: {e}")
        
        # Start background thread
        rebuild_thread = threading.Thread(target=rebuild_in_background, daemon=True)
        rebuild_thread.start()
        
        # Return immediately (don't wait for rebuild)
        return jsonify({
            'message': f'Document {filename} deleted successfully',
            'note': 'Search index rebuilding in background (~30s)'
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    query = data.get('message', '')
    selected_docs = data.get('documents', [])
    web_search_mode = data.get('web_search', False)  # Check if web search is enabled
    
    if not query:
        return jsonify({'error': 'No message provided'}), 400
    
    if web_search_mode:
        # Use web search instead of documents
        try:
            from duckduckgo_search import DDGS
            import traceback
            
            print(f"[Web Search] Searching for: {query}")
            
            # Search web - try different backends for reliability
            results = []
            try:
                ddgs = DDGS()
                # Try with api backend first
                results = ddgs.text(query, max_results=5)
                print(f"[Web Search] Got {len(results)} results")
            except Exception as e1:
                print(f"[Web Search] First attempt failed: {e1}")
                try:
                    # Fallback to html backend
                    ddgs = DDGS()
                    results = ddgs.text(query, max_results=5, backend="html")
                    print(f"[Web Search] Fallback got {len(results)} results")
                except Exception as e2:
                    print(f"[Web Search] All attempts failed: {e2}")
                    traceback.print_exc()
                    results = []
            
            if results:
                # Format search results as context
                context = "Web search results:\n\n"
                for idx, result in enumerate(results, 1):
                    title = result.get('title', '')
                    body = result.get('body', '')
                    href = result.get('href', '')
                    context += f"{idx}. {title}\n{body}\nSource: {href}\n\n"
                
                # Use GitHub Models to answer based on web results
                from openai import OpenAI
                api_key = os.getenv("GITHUB_TOKEN")
                
                if not api_key:
                    return jsonify({'error': 'GitHub token not configured for web search'}), 500
                
                client = OpenAI(
                    base_url="https://models.inference.ai.azure.com",
                    api_key=api_key
                )
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": """You are a helpful assistant. Answer the user's question based on the provided web search results.

Format your response with:
- Clear paragraphs separated by blank lines
- Use **bold** for important terms
- Use bullet points (- ) for lists
- Keep paragraphs concise (2-3 sentences)
- DO NOT use numbered citations like [1], [2] etc.
- Sources are shown separately, so don't list them in your answer"""},
                        {"role": "user", "content": f"Question: {query}\n\n{context}\n\nProvide a clear, well-structured answer with proper paragraph breaks."}
                    ],
                    temperature=0.7
                )
                
                answer = response.choices[0].message.content
                
                # Just the answer - sources are displayed separately by frontend
                formatted_answer = f"**Answer (from web):**\n\n{answer}"
                
                return jsonify({'answer': formatted_answer, 'sources': [r['title'] for r in results]})
            else:
                return jsonify({'answer': 'No web results found.', 'sources': []})
        except Exception as e:
            return jsonify({'answer': f'Web search error: {str(e)}', 'sources': []})
    
    else:
        # Document mode
        answer, sources = qa.ask_question(query, selected_docs)
        # Just the answer - sources are displayed separately by frontend
        formatted_answer = f"**Answer:**\n\n{answer}"
        return jsonify({'answer': formatted_answer, 'sources': sources})

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat():
    qa.clear_memory()
    return jsonify({'message': 'Memory cleared'})

@app.route('/api/quiz', methods=['POST'])
def generate_quiz():
    data = request.json or {}
    selected_docs = data.get('documents', [])
    num_questions = data.get('num_questions', 10)
    difficulty = data.get('difficulty', 'medium')
    
    result = quiz.generate_quiz(selected_docs, num_questions, difficulty)
    return jsonify(result)  # Return result directly, it's already a dict with questions

@app.route('/api/summarize', methods=['POST'])
def get_summary():
    data = request.json
    style = data.get('style', 'Bulleted')
    result = summarize.get_summary(style)
    return jsonify({'summary': result})

@app.route('/api/flashcards', methods=['POST'])
def get_flashcards():
    """Legacy endpoint - generates flashcards without saving"""
    result = flashcards.generate_flashcards()
    return jsonify({'cards': result})

@app.route('/api/flashcards/generate', methods=['POST'])
def generate_and_save_flashcards():
    """Generate flashcards and save them to database"""
    from flashcards import FlashcardManager
    
    # Generate flashcards using AI
    result = flashcards.generate_flashcards()
    
    # Handle error case
    if isinstance(result, dict) and 'error' in result:
        return jsonify(result), 500
    
    # Extract flashcards array from dict response
    cards = result.get('flashcards', []) if isinstance(result, dict) else result
    
    if not cards:
        return jsonify({'error': 'Failed to generate flashcards', 'cards': []}), 500
    
    # Save each flashcard to database
    saved_ids = []
    for card in cards:
        try:
            card_id = FlashcardManager.save_flashcard(
                front=card.get('front', ''),
                back=card.get('back', ''),
                source_document=None,  # TODO: track source document
                deck_name='Default'
            )
            saved_ids.append(card_id)
        except Exception as e:
            print(f"Error saving flashcard: {e}")
    
    return jsonify({
        'cards': cards,
        'saved_count': len(saved_ids),
        'message': f'Generated and saved {len(saved_ids)} flashcards'
    })

@app.route('/api/flashcards/due', methods=['GET'])
def get_due_flashcards():
    """Get all flashcards due for review"""
    from flashcards import FlashcardManager
    
    due_cards = FlashcardManager.get_due_flashcards()
    
    # Convert date objects to strings for JSON serialization
    for card in due_cards:
        if 'next_review_date' in card:
            card['next_review_date'] = str(card['next_review_date'])
        if 'created_at' in card:
            card['created_at'] = str(card['created_at'])
    
    return jsonify({'cards': due_cards, 'count': len(due_cards)})

@app.route('/api/flashcards/review', methods=['POST'])
def submit_flashcard_review():
    """Submit a review for a flashcard"""
    from flashcards import FlashcardManager
    
    data = request.json
    flashcard_id = data.get('flashcard_id')
    quality = data.get('quality')  # Can be 0-5 or "again", "hard", "good", "easy"
    
    if flashcard_id is None or quality is None:
        return jsonify({'error': 'Missing flashcard_id or quality'}), 400
    
    result = FlashcardManager.submit_review(flashcard_id, quality)
    
    if result is None:
        return jsonify({'error': 'Flashcard not found'}), 404
    
    # Convert date to string
    if 'next_review_date' in result:
        result['next_review_date'] = str(result['next_review_date'])
    
    return jsonify({
        'success': True,
        'updated_state': result,
        'message': 'Review submitted successfully'
    })

@app.route('/api/flashcards/stats', methods=['GET'])
def get_flashcard_stats():
    """Get flashcard learning statistics"""
    from flashcards import FlashcardManager
    
    stats = FlashcardManager.get_statistics()
    return jsonify(stats)

@app.route('/api/flashcards/clear', methods=['DELETE'])
def clear_all_flashcards():
    """Delete all flashcards"""
    from flashcards import FlashcardManager
    
    deleted_count = FlashcardManager.delete_all_flashcards()
    return jsonify({
        'deleted_count': deleted_count,
        'message': f'Deleted {deleted_count} flashcards'
    })

@app.route('/api/flashcards/all', methods=['GET'])
def get_all_flashcards():
    """Get all flashcards for browsing"""
    from flashcards import FlashcardManager
    
    all_cards = FlashcardManager.get_all_flashcards()
    
    # Convert date objects to strings
    for card in all_cards:
        if 'next_review_date' in card:
            card['next_review_date'] = str(card['next_review_date'])
        if 'created_at' in card:
            card['created_at'] = str(card['created_at'])
    
    return jsonify({'cards': all_cards, 'count': len(all_cards)})

@app.route('/api/flashcards/<int:id>', methods=['DELETE'])
def delete_flashcard(id):
    """Delete a specific flashcard"""
    from flashcards import FlashcardManager
    
    success = FlashcardManager.delete_flashcard(id)
    
    if success:
        return jsonify({'success': True, 'message': 'Flashcard deleted'})
    else:
        return jsonify({'error': 'Flashcard not found'}), 404

@app.route('/api/mindmap', methods=['POST'])
def get_mindmap():
    result = mindmap.generate_mindmap_code()
    return jsonify({'code': result})

@app.route('/api/mindmap/topics', methods=['POST'])
def get_topics():
    """Extract topics from documents for user selection"""
    data = request.json or {}
    selected_docs = data.get('documents', [])
    result = mindmap.extract_topics_from_docs(selected_docs)
    return jsonify(result)

@app.route('/api/mindmap/generate', methods=['POST'])
def generate_topic_mindmap():
    """Generate mind map for a specific topic"""
    data = request.json
    topic_name = data.get('topic_name', 'General')
    topic_description = data.get('topic_description', '')
    selected_docs = data.get('documents', [])
    
    result = mindmap.generate_mindmap_for_topic(topic_name, topic_description, selected_docs)
    return jsonify({'code': result})

@app.route('/api/knowledge-graph', methods=['POST'])
def get_knowledge_graph():
    """Get 3D knowledge graph data for a specific topic"""
    data = request.json or {}
    topic_name = data.get('topic_name', 'General')
    topic_description = data.get('topic_description', '')
    selected_docs = data.get('documents', [])
    
    result = mindmap.generate_knowledge_graph(topic_name, topic_description, selected_docs)
    return jsonify(result)


@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    audio_path = tts.speak_text(text)
    if audio_path:
        # Return the audio file
        return send_from_directory(os.path.dirname(audio_path), 
                                  os.path.basename(audio_path),
                                  mimetype='audio/mpeg')
    return jsonify({'error': 'TTS failed'}), 500

if __name__ == '__main__':
    os.makedirs('data/temp', exist_ok=True)
    app.run(debug=True, port=5000)
