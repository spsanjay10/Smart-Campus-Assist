# Smart Campus Assist 🎓

An AI-powered study companion with an elegant, Apple-inspired web interface. Upload your PDFs and let AI help you learn through chat, flashcards, mind maps, quizzes, and more.

![Smart Campus Assist](https://img.shields.io/badge/AI-Powered-blue) ![Python](https://img.shields.io/badge/Python-3.8+-green) ![Flask](https://img.shields.io/badge/Flask-Backend-red)

## ✨ Features

### 📚 Document Library
- Drag & drop PDF upload
- Automatic text extraction and indexing
- Vector-based semantic search with FAISS

### 💬 Study Chat
- AI-powered Q&A with document context
- Conversation memory for follow-up questions
- Source citations for answers
- **Web Search Mode** - Toggle to search the internet
- Voice mode with text-to-speech responses

### 🛠️ Toolkit
| Tool | Description |
|------|-------------|
| **Summarizer** | Generate bullet points, detailed, or outline summaries |
| **Flashcards** | Auto-generate study cards from your documents |
| **Mind Map** | 2D Mermaid diagrams for concept visualization |
| **3D Knowledge Graph** | Interactive 3D graph of connected concepts |

### 📊 Quiz Generator
- Multiple choice questions from your documents
- Three difficulty levels: Easy (5), Medium (10), Hard (15)
- Document-specific question generation
- Instant answer feedback

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/spsanjay10/Smart-Campus-Assist.git
   cd Smart-Campus-Assist
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the root directory:
   ```env
   GITHUB_TOKEN=your_github_models_api_key
   GROQ_API_KEY=your_groq_api_key
   ```
   
   > **Getting API Keys:**
   > - [GitHub Models](https://github.com/marketplace/models) - For GPT-4o mini
   > - [Groq](https://console.groq.com/) - For Llama 3.3 70B

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open in browser**
   ```
   http://localhost:5000
   ```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Flask REST API |
| **Frontend** | HTML, CSS, JavaScript |
| **AI Models** | GPT-4o mini (GitHub), Llama 3.3 70B (Groq) |
| **Vector DB** | FAISS with HuggingFace Embeddings |
| **Web Search** | DuckDuckGo |
| **TTS** | Google Text-to-Speech (gTTS) |
| **UI Design** | Apple-inspired Glassmorphism |

## 📁 Project Structure

```
Smart-Campus-Assist/
├── app.py              # Main Flask application
├── qa.py               # Question-answering logic
├── quiz.py             # Quiz generation
├── flashcards.py       # Flashcard management & SRS
├── mindmap.py          # Mind map & 3D graph generation
├── summarize.py        # Document summarization
├── ingest.py           # PDF processing & FAISS indexing
├── tts.py              # Text-to-speech
├── srs_algorithm.py    # Spaced repetition (SM-2)
├── requirements.txt    # Python dependencies
├── static/
│   ├── css/style.css   # Styling
│   ├── js/app.js       # Frontend JavaScript
│   └── index.html      # Main HTML page
└── data/               # Generated data (gitignored)
    ├── faiss_index/    # Vector embeddings
    └── metadata.db     # SQLite database
```

## 🎨 Screenshots

The application features a modern, dark-themed UI with:
- Glassmorphism effects
- Smooth animations
- Responsive design
- Interactive 3D visualizations

## 📝 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload PDF documents |
| `/api/chat` | POST | Send chat messages |
| `/api/summarize` | POST | Generate summaries |
| `/api/quiz` | POST | Generate quiz questions |
| `/api/flashcards/generate` | POST | Generate flashcards |
| `/api/mindmap/topics` | POST | Extract topics |
| `/api/mindmap/generate` | POST | Generate mind map |
| `/api/knowledge-graph` | POST | Generate 3D graph |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## 🙏 Acknowledgments

- [LangChain](https://langchain.com/) for document processing
- [FAISS](https://github.com/facebookresearch/faiss) for vector search
- [3D Force Graph](https://github.com/vasturiano/3d-force-graph) for 3D visualization
- [Mermaid](https://mermaid.js.org/) for diagram generation

---
