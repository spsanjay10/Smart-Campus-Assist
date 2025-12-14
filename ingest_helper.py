# Helper function for background indexing
import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")

def index_documents_only(temp_files):
    """Index documents without database operations (for background upload)"""
    documents = []
    
    for file in temp_files:
        try:
            loader = PyPDFLoader(file.name)
            docs = loader.load()
            documents.extend(docs)
        except Exception as e:
            print(f"Error loading {os.path.basename(file.name)}: {e}")
            continue
    
    if not documents:
        return "No documents to index"
    
    # Split documents
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(documents)
    
    # Force CPU usage for thread safety
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={'device': 'cpu'}
    )
    
    # Update or create FAISS index
    try:
        if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(os.path.join(FAISS_INDEX_PATH, "index.faiss")):
            vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
            vectorstore.add_documents(splits)
        else:
            vectorstore = FAISS.from_documents(splits, embeddings)
        
        vectorstore.save_local(FAISS_INDEX_PATH)
    except Exception as e:
        print(f"Index creation failed: {e}")
        vectorstore = FAISS.from_documents(splits, embeddings)
        vectorstore.save_local(FAISS_INDEX_PATH)
    
    return f"Indexed {len(splits)} chunks from {len(temp_files)} files"
