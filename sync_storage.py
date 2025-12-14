import os
import sqlite3
import glob
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

DATA_DIR = "data"
TEMP_DIR = os.path.join(DATA_DIR, "temp")
DB_PATH = os.path.join(DATA_DIR, "metadata.db")
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")

def sync_database_with_files():
    """Sync database with files in data/temp directory"""
    
    print("=== SYNCHRONIZING STORAGE ===\n")
    
    # Get files from filesystem
    pdf_files = glob.glob(os.path.join(TEMP_DIR, "*.pdf"))
    fs_filenames = {os.path.basename(f) for f in pdf_files}
    print(f"Files in {TEMP_DIR}: {len(fs_filenames)}")
    for f in sorted(fs_filenames):
        print(f"  • {f}")
    
    # Get files from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT filename FROM uploads')
    db_filenames = {row[0] for row in cursor.fetchall()}
    print(f"\nFiles in database: {len(db_filenames)}")
    for f in sorted(db_filenames):
        print(f"  • {f}")
    
    # Find mismatches
    missing_in_db = fs_filenames - db_filenames
    missing_in_fs = db_filenames - fs_filenames
    
    print(f"\n--- SYNC ACTIONS ---")
    
    # Add missing files to database
    if missing_in_db:
        print(f"\nAdding {len(missing_in_db)} files to database:")
        for filename in sorted(missing_in_db):
            print(f"  + {filename}")
            cursor.execute('INSERT INTO uploads (filename) VALUES (?)', (filename,))
        conn.commit()
    else:
        print("\n✓ No files to add to database")
    
    # Remove orphaned database entries
    if missing_in_fs:
        print(f"\nRemoving {len(missing_in_fs)} orphaned entries from database:")
        for filename in sorted(missing_in_fs):
            print(f"  - {filename}")
            cursor.execute('DELETE FROM uploads WHERE filename = ?', (filename,))
        conn.commit()
    else:
        print("\n✓ No orphaned database entries")
    
    conn.close()
    
    # Rebuild FAISS index with ALL files
    print(f"\n--- REBUILDING FAISS INDEX ---")
    
    if not pdf_files:
        print("No PDF files found")
        return
    
    documents = []
    
    for pdf_path in sorted(pdf_files):
        filename = os.path.basename(pdf_path)
        try:
            print(f"Loading {filename}...")
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            documents.extend(docs)
            print(f"  ✓ {len(docs)} pages loaded")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
    
    if not documents:
        print("No documents to index")
        return
    
    # Split documents
    print(f"\nSplitting {len(documents)} pages into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(documents)
    print(f"  ✓ Created {len(splits)} chunks")
    
    # Create FAISS index
    print("\nCreating FAISS index...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(splits, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)
    print(f"  ✓ FAISS index saved")
    
    # Verify index
    print("\n--- VERIFICATION ---")
    docs = vectorstore.similarity_search("test", k=100)
    source_counts = {}
    for doc in docs:
        source = doc.metadata.get('source', '')
        filename = os.path.basename(source)
        source_counts[filename] = source_counts.get(filename, 0) + 1
    
    print(f"\nFAISS index contains {len(docs)} chunks from {len(source_counts)} files:")
    for filename, count in sorted(source_counts.items()):
        print(f"  • {filename}: {count} chunks")
    
    print("\n✓ SYNCHRONIZATION COMPLETE!")

if __name__ == "__main__":
    sync_database_with_files()
