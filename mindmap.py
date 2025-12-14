import os
import json
from groq import Groq
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv

load_dotenv()
DATA_DIR = "data"
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss_index")

def generate_mindmap_code():
    """Generate Mermaid.js syntax for 2D mind map using Groq"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return "graph TD; A[Error] --> B[GROQ_API_KEY Missing];"
    
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not os.path.exists(FAISS_INDEX_PATH): return "graph TD; A[Empty] --> B[Upload Docs];"
    
    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 8}) 
        docs = retriever.invoke("overview structure hierarchy relationships")
        context = "\n".join([d.page_content for d in docs])
    except:
        return "graph TD; A[Error] --> B[Retrieval Failed];"

    # Use Groq for 2D mind map
    client = Groq(api_key=api_key)
    
    prompt = f"""
Create a mind map in Mermaid.js format from this text.

STRICT RULES:
1. Start with: graph TD
2. Use ONLY this format: ID[Short Text]
3. Connect with: ID1 --> ID2  
4. IDs must be simple: A, B, C, D (no special chars)
5. Text must be SHORT (max 3-4 words)
6. NO quotes, colons, or special characters in labels
7. Maximum 8 nodes

Example:
graph TD
    A[Main Topic]
    A --> B[First Point]
    A --> C[Second Point]
    B --> D[Detail]

Text: {context[:3000]}

Return ONLY the Mermaid code:"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2  # Lower temperature for more consistent output
        )
        code = response.choices[0].message.content.strip()
        
        # Clean markdown code blocks
        if code.startswith("```mermaid"): code = code[10:]
        if code.startswith("```"): code = code[3:]
        if code.endswith("```"): code = code[:-3]
        code = code.strip()
        
        # Ensure starts with graph TD
        if not code.startswith("graph"):
            code = "graph TD\n" + code
        
        # Remove problematic characters
        code = code.replace('"', '').replace("'", "").replace(":", "")
        
        return code
    except:
        return "graph TD; A[Error] --> B[Generation Failed];"

def extract_topics_from_docs(selected_docs=None):
    """Extract main topics from documents for user selection"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY missing", "topics": []}
    
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not os.path.exists(FAISS_INDEX_PATH):
        return {"error": "No documents uploaded", "topics": []}
    
    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        
        print(f"\n=== TOPIC EXTRACTION DEBUG ===")
        print(f"Selected documents from frontend: {selected_docs}")
        
        # If specific documents are selected, we need to get ALL docs and filter by source
        if selected_docs and len(selected_docs) > 0:
            # Normalize selected docs for comparison
            normalized_selected = [d.lower().strip() for d in selected_docs]
            print(f"Normalized selected: {normalized_selected}")
            
            # Get ALL documents from the vectorstore by using a very large k
            # or by accessing the docstore directly
            all_docs_dict = vectorstore.docstore._dict
            print(f"Total chunks in vectorstore: {len(all_docs_dict)}")
            
            # Filter documents by source filename
            filtered_docs = []
            for doc_id, doc in all_docs_dict.items():
                doc_source = doc.metadata.get('source', '')
                doc_filename = os.path.basename(doc_source).lower().strip()
                
                # Check if this doc matches any selected document
                for sel in normalized_selected:
                    if doc_filename == sel or sel in doc_filename or doc_filename in sel:
                        filtered_docs.append(doc)
                        break
            
            print(f"Found {len(filtered_docs)} chunks matching selected documents")
            
            if len(filtered_docs) == 0:
                # List all unique filenames for debugging
                all_filenames = set()
                for doc in all_docs_dict.values():
                    fn = os.path.basename(doc.metadata.get('source', '')).lower()
                    all_filenames.add(fn)
                print(f"Available filenames in vectorstore: {all_filenames}")
                return {"error": f"No content found for selected documents. Available: {list(all_filenames)}", "topics": []}
            
            docs = filtered_docs
        else:
            # No specific selection - use semantic search
            retriever = vectorstore.as_retriever(search_kwargs={"k": 15})
            docs = retriever.invoke("main topics concepts themes subjects overview")
        
        print(f"Using {len(docs)} document chunks for topic extraction")
        
        if not docs or len(docs) == 0:
            return {"error": "No content found in selected documents", "topics": []}
            
        context = "\n".join([d.page_content for d in docs[:30]])  # Limit to avoid token limits
        print(f"Final context length: {len(context)} characters")
        print(f"=== END DEBUG ===\n")
    except Exception as e:
        print(f"Error extracting topics: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "topics": []}
    
    client = Groq(api_key=api_key)
    
    prompt = f"""Extract 5-8 main topics/themes from this text.

Return ONLY a JSON array of topic objects:
[
  {{"id": 1, "name": "Topic Name", "description": "Brief 10-word description"}},
  {{"id": 2, "name": "Another Topic", "description": "Brief description"}}
]

Rules:
- Extract distinct, meaningful topics
- Keep names short (2-4 words)
- Keep descriptions under 15 words
- Return ONLY valid JSON array

Text: {context[:4000]}

JSON:"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean markdown
        if result.startswith("```json"): result = result[7:]
        if result.startswith("```"): result = result[3:]
        if result.endswith("```"): result = result[:-3]
        result = result.strip()
        
        topics = json.loads(result)
        return {"topics": topics, "error": None}
        
    except Exception as e:
        return {"error": str(e), "topics": [
            {"id": 1, "name": "General Overview", "description": "Overview of all document content"}
        ]}

def generate_mindmap_for_topic(topic_name, topic_description="", selected_docs=None):
    """Generate mind map for a specific topic"""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key: return "graph TD; A[Error] --> B[GROQ_API_KEY Missing];"
    
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not os.path.exists(FAISS_INDEX_PATH): return "graph TD; A[Empty] --> B[Upload Docs];"
    
    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
        # Search specifically for the chosen topic
        docs = retriever.invoke(f"{topic_name} {topic_description}")
        
        # Filter by selected documents if provided
        if selected_docs and len(selected_docs) > 0:
            filtered_docs = []
            for doc in docs:
                doc_source = doc.metadata.get('source', '')
                # Extract just the filename from the full path
                doc_filename = os.path.basename(doc_source)
                # Check if this document is in the selected list
                if doc_filename in selected_docs:
                    filtered_docs.append(doc)
            docs = filtered_docs if filtered_docs else docs  # Fallback to all if no matches
        
        if not docs or len(docs) == 0:
            return "graph TD; A[No Content] --> B[No matching documents found];"
            
        context = "\n".join([d.page_content for d in docs])
    except Exception as e:
        print(f"Error in mindmap generation: {e}")
        return "graph TD; A[Error] --> B[Retrieval Failed];"

    client = Groq(api_key=api_key)
    
    prompt = f"""Create a detailed mind map about "{topic_name}" using Mermaid.js.

STRICT RULES:
1. Start with: graph TD
2. Use format: ID[Short Text]
3. Connect with: ID1 --> ID2
4. IDs: A, B, C, D, E, F, G, H, I, J (simple letters)
5. Text: 2-5 words max
6. NO quotes, colons, or special characters
7. Create 10-15 nodes for detail
8. Main topic as root node A
9. Create 3-4 subtopics branching from A
10. Add 2-3 details under each subtopic

Topic: {topic_name}
Description: {topic_description}

Relevant Content: {context[:3500]}

Return ONLY the Mermaid code:"""
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.25
        )
        code = response.choices[0].message.content.strip()
        
        # Clean
        if code.startswith("```mermaid"): code = code[10:]
        if code.startswith("```"): code = code[3:]
        if code.endswith("```"): code = code[:-3]
        code = code.strip()
        
        if not code.startswith("graph"):
            code = "graph TD\n" + code
        
        code = code.replace('"', '').replace("'", "").replace(":", " -")
        
        return code
    except:
        return "graph TD; A[Error] --> B[Generation Failed];"


def generate_knowledge_graph(topic_name="General", topic_description="", selected_docs=None):
    """Generate 3D knowledge graph data using GitHub Models GPT-4o mini"""
    api_key = os.getenv("GITHUB_TOKEN")
    if not api_key:
        return {"error": "GITHUB_TOKEN missing", "nodes": [], "edges": []}
    
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if not os.path.exists(FAISS_INDEX_PATH):
        return {"nodes": [{"id": 1, "name": "No Documents", "group": 1}], "links": []}
    
    try:
        vectorstore = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        
        # Use more documents if filtering
        search_k = 20 if selected_docs else 10
        retriever = vectorstore.as_retriever(search_kwargs={"k": search_k})
        
        # Search for the specific topic
        search_query = f"{topic_name} {topic_description} concepts relationships structure"
        docs = retriever.invoke(search_query)
        
        print(f"\n=== 3D GRAPH DEBUG ===")
        print(f"Topic: {topic_name}")
        print(f"Selected documents: {selected_docs}")
        print(f"Retrieved {len(docs)} documents from FAISS")
        
        # Filter by selected documents if provided
        if selected_docs and len(selected_docs) > 0:
            filtered_docs = []
            for doc in docs:
                doc_source = doc.metadata.get('source', '')
                doc_filename = os.path.basename(doc_source)
                if doc_filename in selected_docs:
                    filtered_docs.append(doc)
            
            print(f"Filtered to {len(filtered_docs)} documents")
            docs = filtered_docs if filtered_docs else docs
        
        if not docs:
            return {"nodes": [{"id": 1, "name": "No Content", "group": 1}], "links": []}
            
        context = "\n".join([d.page_content for d in docs])
        print(f"Context length: {len(context)} characters")
        print(f"=== END DEBUG ===\n")
    except Exception as e:
        return {"error": str(e), "nodes": [], "links": []}
    
    # Use GitHub Models for 3D graph
    from openai import OpenAI
    
    client = OpenAI(
        base_url="https://models.inference.ai.azure.com",
        api_key=api_key
    )
    
    prompt = f"""Create a 3D knowledge graph about "{topic_name}" from this text.

Return ONLY valid JSON in this exact format:
{{
  "nodes": [
    {{"id": 1, "name": "Concept Name", "group": 1, "val": 10, "description": "Brief description"}},
    {{"id": 2, "name": "Another Concept", "group": 1, "val": 8, "description": "Description"}}
  ],
  "links": [
    {{"source": 1, "target": 2, "value": 1, "type": "relates_to"}}
  ]
}}

Rules:
- Focus on concepts related to "{topic_name}"
- Use simple integer IDs starting from 1
- Keep node names very short (2-4 words max)
- Group related concepts with same group number (1-5)
- val is importance (1-15)
- Keep total nodes under 20
- Links connect related concepts

Topic: {topic_name}
Description: {topic_description}

Text: {context[:4000]}

Return ONLY the JSON:"""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        result = response.choices[0].message.content.strip()
        
        # Clean markdown code blocks
        if result.startswith("```json"): result = result[7:]
        if result.startswith("```"): result = result[3:]
        if result.endswith("```"): result = result[:-3]
        result = result.strip()
        
        # Parse JSON
        graph_data = json.loads(result)
        
        # Validate structure
        if "nodes" not in graph_data or "links" not in graph_data:
            return {"nodes": [{"id": 1, "name": "Parse Error", "group": 1}], "links": []}
        
        return graph_data
        
    except Exception as e:
        print(f"3D Graph Error: {e}")
        return {
            "nodes": [
                {"id": 1, "name": "Error", "group": 1, "val": 10, "description": str(e)}
            ],
            "links": []
        }
