import os
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")

embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

if os.path.exists(FAISS_INDEX_PATH):
    vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    
    # Get all documents
    docs = vectorstore.similarity_search("test", k=50)
    
    # Extract unique source filenames
    sources = set()
    for doc in docs:
        source = doc.metadata.get('source', '')
        filename = os.path.basename(source)
        sources.add(filename)
    
    print("\n=== FAISS Stored Filenames ===")
    for src in sorted(sources):
        print(f"  • {src}")
    print(f"Total unique files: {len(sources)}")
else:
    print("FAISS index not found!")
