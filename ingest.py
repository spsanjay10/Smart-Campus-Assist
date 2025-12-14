import os
import sqlite3
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")
DB_PATH = os.path.join(DATA_DIR, "metadata.db")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Uploads table with UNIQUE constraint on filename
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Flashcards table with SM-2 algorithm fields
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            front TEXT NOT NULL,
            back TEXT NOT NULL,
            source_document TEXT,
            deck_name TEXT DEFAULT 'Default',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            easiness_factor REAL DEFAULT 2.5,
            repetition_count INTEGER DEFAULT 0,
            interval_days INTEGER DEFAULT 1,
            next_review_date DATE DEFAULT (date('now'))
        )
    ''')
    
    # Reviews table for tracking review history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flashcard_id INTEGER NOT NULL,
            quality_rating INTEGER NOT NULL,
            reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE CASCADE
        )
    ''')
    
    # Chat history table for persistent conversation memory
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def ingest_docs(files):
    if not files:
        return "No files provided."

    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get existing filenames
    cursor.execute('SELECT filename FROM uploads')
    existing_files = set(row[0] for row in cursor.fetchall())
    
    documents = []
    new_files = []
    skipped_files = []
    
    for file in files:
        filename = os.path.basename(file.name)
        
        # Check for duplicates
        if filename in existing_files:
            print(f"Skipping duplicate file: {filename}")
            skipped_files.append(filename)
            continue
        
        # Add to database
        cursor.execute('INSERT INTO uploads (filename) VALUES (?)', (filename,))
        existing_files.add(filename)  # Update set to catch duplicates in same batch
        new_files.append(filename)
        
        try:
            loader = PyPDFLoader(file.name)
            # PyPDFLoader automatically adds 'page' and 'source' to metadata
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
            
    conn.commit()
    conn.close()

    if not documents:
        return "No valid documents found."

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(documents)

    # Force CPU usage for thread safety
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'}
    )
    
    try:
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(os.path.join(FAISS_INDEX_PATH, "index.faiss")):
            vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
            vectorstore.add_documents(splits)
        else:
            vectorstore = FAISS.from_documents(splits, embeddings)
        
        vectorstore.save_local(FAISS_INDEX_PATH)
    except Exception as e:
        print(f"Index creation failed: {e}")
        # Fallback create new
        vectorstore = FAISS.from_documents(splits, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)

    result_msg = f"Successfully processed {len(new_files)} new file(s). Total chunks: {len(splits)}"
    if skipped_files:
        result_msg += f"\nSkipped {len(skipped_files)} duplicate(s): {', '.join(skipped_files)}"
    
    return result_msg

def get_uploaded_documents():
    """Get list of all uploaded documents"""
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT filename FROM uploads ORDER BY upload_time DESC')
    rows = cursor.fetchall()
    
    conn.close()
    
    return [row[0] for row in rows]

def rebuild_faiss_index():
    """Rebuild FAISS index from all documents in data/temp directory"""
    import glob
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    print("=== Rebuilding FAISS Index ===")
    
    # Get all PDF files from temp directory
    pdf_files = glob.glob(os.path.join(DATA_DIR, 'temp', '*.pdf'))
    
    if not pdf_files:
        print("No PDF files found to rebuild index")
        # Remove FAISS index if it exists
        if os.path.exists(FAISS_INDEX_PATH):
            import shutil
            shutil.rmtree(FAISS_INDEX_PATH)
        return "No documents to index"
    
    documents = []
    
    for pdf_path in pdf_files:
        try:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            documents.extend(docs)
            print(f"Loaded: {os.path.basename(pdf_path)} ({len(docs)} pages)")
        except Exception as e:
            print(f"Error loading {pdf_path}: {e}")
            continue
    
    if not documents:
        return "No valid documents to index"
    
    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(documents)
    
    # Create new FAISS index (force CPU for thread safety)
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'}
    )
    vectorstore = FAISS.from_documents(splits, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)
    
    print(f"✓ Rebuilt FAISS index with {len(splits)} chunks from {len(pdf_files)} files")
    
    return f"Index rebuilt: {len(splits)} chunks from {len(pdf_files)} files"
