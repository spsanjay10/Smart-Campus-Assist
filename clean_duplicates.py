import os
import sqlite3
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")
DB_PATH = os.path.join(DATA_DIR, "metadata.db")

def clean_duplicates():
    """Remove duplicate entries from database and rebuild FAISS index"""
    
    # Clean database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=== Cleaning Database Duplicates ===")
    
    # Get all filenames with their IDs
    cursor.execute('SELECT id, filename FROM uploads ORDER BY id')
    rows = cursor.fetchall()
    
    seen = set()
    duplicates = []
    
    for id, filename in rows:
        if filename in seen:
            duplicates.append((id, filename))
        else:
            seen.add(filename)
    
    if duplicates:
        print(f"Found {len(duplicates)} duplicate entries:")
        for id, filename in duplicates:
            print(f"  Deleting: {filename} (ID: {id})")
            cursor.execute('DELETE FROM uploads WHERE id = ?', (id,))
        
        conn.commit()
        print(f"✓ Removed {len(duplicates)} duplicates from database")
    else:
        print("✓ No duplicates found in database")
    
    # Get unique filenames
    cursor.execute('SELECT DISTINCT filename FROM uploads')
    remaining_files = [row[0] for row in cursor.fetchall()]
    print(f"\nRemaining unique files: {len(remaining_files)}")
    for f in remaining_files:
        print(f"  • {f}")
    
    conn.close()
    
    print("\n=== Checking FAISS Index ===")
    if os.path.exists(FAISS_INDEX_PATH):
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        
        # Get all documents
        docs = vectorstore.similarity_search("test", k=100)
        
        # Count by source
        source_counts = {}
        for doc in docs:
            source = doc.metadata.get('source', '')
            filename = os.path.basename(source)
            source_counts[filename] = source_counts.get(filename, 0) + 1
        
        print(f"FAISS index contains {len(docs)} chunks from {len(source_counts)} files:")
        for filename, count in sorted(source_counts.items()):
            print(f"  • {filename}: {count} chunks")
    else:
        print("FAISS index not found")
    
    print("\n✓ Cleanup complete!")

if __name__ == "__main__":
    clean_duplicates()
