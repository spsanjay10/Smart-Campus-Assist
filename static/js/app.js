// Wait for DOM and Mermaid to load
document.addEventListener('DOMContentLoaded', () => {
    // Initialize Mermaid after it's loaded
    if (typeof mermaid !== 'undefined') {
        mermaid.initialize({ startOnLoad: false, theme: 'dark' });
    }
});

const API_BASE = 'http://localhost:5000/api';

// Global state
let selectedDocuments = [];

// Sidebar Navigation
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        const tabName = item.dataset.tab;

        // Update active states
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.content-section').forEach(c => c.classList.remove('active'));

        item.classList.add('active');
        document.getElementById(tabName).classList.add('active');
    });
});

// File Upload
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const uploadStatus = document.getElementById('uploadStatus');

// Make upload area clickable
uploadArea.addEventListener('click', () => {
    fileInput.click();
});

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
    uploadArea.addEventListener(eventName, preventDefaults, false);
});

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

['dragenter', 'dragover'].forEach(eventName => {
    uploadArea.addEventListener(eventName, () => uploadArea.classList.add('highlight'), false);
});

['dragleave', 'drop'].forEach(eventName => {
    uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('highlight'), false);
});

uploadArea.addEventListener('drop', handleDrop, false);
fileInput.addEventListener('change', e => handleFiles(e.target.files));

function handleDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
}

async function handleFiles(files) {
    // ALWAYS get fresh list of existing documents (important after deletions!)
    let existingDocs = [];
    try {
        const response = await fetch(`${API_BASE}/documents`);
        const data = await response.json();
        existingDocs = data.documents || [];
        console.log('Current documents in database:', existingDocs);
    } catch (error) {
        console.error('Error fetching existing documents:', error);
    }

    const formData = new FormData();
    const duplicates = [];
    const validFiles = [];

    Array.from(files).forEach(file => {
        if (file.type === 'application/pdf') {
            // Check if file already exists
            if (existingDocs.includes(file.name)) {
                duplicates.push(file.name);
            } else {
                formData.append('files', file);
                validFiles.push(file.name);
            }
        }
    });

    // If all files are duplicates, show error and stop
    if (validFiles.length === 0 && duplicates.length > 0) {
        uploadStatus.textContent = `❌ All files already uploaded: ${duplicates.join(', ')}`;
        uploadStatus.className = 'upload-status error';
        uploadStatus.style.display = 'block';
        setTimeout(() => {
            uploadStatus.style.display = 'none';
        }, 5000);
        return;
    }

    // If some duplicates, show warning
    if (duplicates.length > 0) {
        uploadStatus.textContent = `⚠️ Skipping duplicates: ${duplicates.join(', ')}`;
        uploadStatus.className = 'upload-status';
        uploadStatus.style.display = 'block';
    }

    // If no valid files, stop
    if (validFiles.length === 0) {
        uploadStatus.textContent = '❌ No valid PDF files to upload';
        uploadStatus.className = 'upload-status error';
        uploadStatus.style.display = 'block';
        return;
    }

    uploadStatus.textContent = `Uploading ${validFiles.length} file(s)...`;
    uploadStatus.className = 'upload-status';
    uploadStatus.style.display = 'block';

    try {
        const response = await fetch(`${API_BASE}/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (response.ok) {
            // Show success with background note
            uploadStatus.textContent = data.message || 'Upload successful!';
            if (data.note) {
                uploadStatus.textContent += ` (${data.note})`;
            }
            uploadStatus.className = 'upload-status success';
            uploadStatus.style.display = 'block';

            // Reload documents list after a delay
            setTimeout(loadDocuments, 1000);

            // Clear message after 8 seconds (but keep element visible)
            setTimeout(() => {
                uploadStatus.textContent = '';
                uploadStatus.className = 'upload-status';
            }, 8000);
        } else {
            uploadStatus.textContent = data.error || 'Upload failed. Please try again.';
            uploadStatus.className = 'upload-status error';
            uploadStatus.style.display = 'block';
        }
    } catch (error) {
        console.error('Upload error:', error);
        uploadStatus.textContent = 'Upload failed. Please try again.';
        uploadStatus.className = 'upload-status error';
        uploadStatus.style.display = 'block';
    }
}

// Document Management
async function loadDocuments() {
    try {
        const response = await fetch(`${API_BASE}/documents`);
        const data = await response.json();

        if (data.documents && data.documents.length > 0) {
            displayDocuments(data.documents);
            displayDocumentFilters(data.documents);
        }
    } catch (error) {
        console.error('Error loading documents:', error);
    }
}

function displayDocuments(documents) {
    const docsList = document.getElementById('documentsList');
    const docsSection = document.getElementById('documentsSection');

    if (!docsList) return;

    docsSection.style.display = 'block';
    docsList.innerHTML = documents.map(doc => `
        <div class="document-card" data-filename="${doc}">
            <span class="document-icon">📄</span>
            <span class="document-name" title="${doc}">${doc}</span>
            <button class="btn-delete-doc" data-doc="${doc}" title="Delete document">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    <line x1="10" y1="11" x2="10" y2="17"></line>
                    <line x1="14" y1="11" x2="14" y2="17"></line>
                </svg>
            </button>
        </div>
    `).join('');

    // Add delete button handlers
    docsList.querySelectorAll('.btn-delete-doc').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const filename = btn.dataset.doc;

            if (confirm(`Delete "${filename}"? This cannot be undone.`)) {
                const statusDiv = document.getElementById('uploadStatus');

                try {
                    // Show deleting message
                    statusDiv.textContent = `🗑️ Deleting "${filename}"...`;
                    statusDiv.style.display = 'block';
                    statusDiv.style.color = '#0A84FF';

                    const response = await fetch(`${API_BASE}/documents/${encodeURIComponent(filename)}`, {
                        method: 'DELETE'
                    });

                    if (response.ok) {
                        const data = await response.json();

                        // Show success with background note
                        statusDiv.textContent = `✅ ${data.message}. ${data.note || ''}`;
                        statusDiv.style.color = '#30D158';

                        // Remove from UI immediately
                        btn.closest('.document-card').remove();

                        // Reload documents list after delay to ensure DB is updated
                        await new Promise(resolve => setTimeout(resolve, 500));
                        await loadDocuments();

                        // Clear status after 5 seconds
                        setTimeout(() => {
                            statusDiv.textContent = '';
                            statusDiv.style.color = '';
                        }, 5000);
                    } else {
                        statusDiv.textContent = '❌ Failed to delete document';
                        statusDiv.style.color = '#FF453A';
                    }
                } catch (error) {
                    console.error('Delete error:', error);
                    statusDiv.textContent = '❌ Error deleting document';
                    statusDiv.style.color = '#FF453A';
                }
            }
        });
    });
}

function displayDocumentFilters(documents) {
    // Show filters for Chat
    const filterSection = document.getElementById('documentFilter');
    const chipsContainer = document.getElementById('documentChips');

    if (chipsContainer) {
        filterSection.style.display = 'block';
        chipsContainer.innerHTML = documents.map(doc => `
            <div class="doc-chip" data-doc="${doc}">${doc}</div>
        `).join('');

        // Add click handlers
        document.querySelectorAll('#documentChips .doc-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                chip.classList.toggle('selected');
                updateSelectedDocuments();
            });
        });
    }

    // Show filters for Toolkit tools (Summarizer, Flashcards, Mind Map, Quiz)
    const toolSections = ['summarizer', 'flashcards', 'mindmap', 'quiz'];
    toolSections.forEach(section => {
        const filterDiv = document.getElementById(`${section}DocFilter`);
        const chips = document.getElementById(`${section}DocChips`);

        if (filterDiv && chips) {
            filterDiv.style.display = 'block';
            chips.innerHTML = documents.map(doc => `
                <div class="doc-chip" data-doc="${doc}" data-section="${section}">${doc}</div>
            `).join('');

            // Add click handlers for this section
            chips.querySelectorAll('.doc-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    chip.classList.toggle('selected');
                });
            });
        }
    });
}

function updateSelectedDocuments() {
    selectedDocuments = Array.from(document.querySelectorAll('#documentChips .doc-chip.selected'))
        .map(chip => chip.dataset.doc);
}

// Get selected documents for a specific section
function getSelectedDocsForSection(section) {
    const chips = document.querySelectorAll(`#${section}DocChips .doc-chip.selected`);
    return Array.from(chips).map(chip => chip.dataset.doc);
}

// Toggle all documents for a section
window.toggleAllDocs = function (section) {
    const chips = document.querySelectorAll(`#${section}DocChips .doc-chip`);
    const allSelected = Array.from(chips).every(chip => chip.classList.contains('selected'));

    chips.forEach(chip => {
        if (allSelected) {
            chip.classList.remove('selected');
        } else {
            chip.classList.add('selected');
        }
    });
};

// Select/Clear buttons (set up after DOM loads)
document.addEventListener('DOMContentLoaded', () => {
    loadDocuments();

    const selectAll = document.getElementById('selectAllDocs');
    const clearAll = document.getElementById('clearSelection');

    if (selectAll) {
        selectAll.addEventListener('click', () => {
            document.querySelectorAll('.doc-chip').forEach(c => c.classList.add('selected'));
            updateSelectedDocuments();
        });
    }

    if (clearAll) {
        clearAll.addEventListener('click', () => {
            document.querySelectorAll('.doc-chip').forEach(c => c.classList.remove('selected'));
            updateSelectedDocuments();
        });
    }
});

// Chat
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const voiceMode = document.getElementById('voiceMode');
const clearMemory = document.getElementById('clearMemory');

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keypress', e => {
    if (e.key === 'Enter') sendMessage();
});

// Web search mode toggle
let isWebSearchMode = false;

document.getElementById('webSearchToggle')?.addEventListener('click', () => {
    isWebSearchMode = !isWebSearchMode;
    const toggle = document.getElementById('webSearchToggle');
    const modeText = document.getElementById('searchModeText');
    // chatInput already defined globally on line 246
    const docFilter = document.getElementById('documentFilter');

    if (isWebSearchMode) {
        toggle.classList.add('active');
        modeText.textContent = 'Web Search';
        chatInput.placeholder = 'Ask anything - searching the web...';
        docFilter.style.display = 'none';
    } else {
        toggle.classList.remove('active');
        modeText.textContent = 'Documents';
        chatInput.placeholder = 'Ask me anything...';
        const documentsList = document.querySelectorAll('.document-card');
        if (documentsList.length > 0) {
            docFilter.style.display = 'block';
        }
    }
});

async function sendMessage() {
    const message = chatInput.value.trim();
    if (!message) return;

    // Add user message
    addMessage(message, 'user');
    chatInput.value = '';

    // Show typing indicator
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'message assistant typing-indicator';
    typingIndicator.innerHTML = `
        <div class="typing-dots">
            <span></span><span></span><span></span>
        </div>
        <span class="typing-text">Thinking...</span>
    `;
    chatMessages.appendChild(typingIndicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message,
                documents: selectedDocuments,
                web_search: isWebSearchMode  // Pass web search mode
            })
        });
        const data = await response.json();

        // Remove typing indicator
        typingIndicator.remove();

        // Add assistant message
        addMessage(data.answer, 'assistant');

        // Show sources if available
        if (data.sources && data.sources.length > 0) {
            const sourcesText = '📚 Sources: ' + data.sources.join(', ');
            addMessage(sourcesText, 'sources');
        }

        // Play audio if voice mode is enabled
        if (voiceMode.checked) {
            playAudio(data.answer);
        }
    } catch (error) {
        typingIndicator.remove();
        addMessage('Error: Could not get response', 'assistant');
        console.error('Chat error:', error);
    }
}

function addMessage(text, type) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${type}`;

    // Parse markdown for assistant messages
    if (type === 'assistant') {
        msgDiv.innerHTML = parseMarkdown(text);
    } else {
        msgDiv.textContent = text;
    }

    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Enhanced markdown parser for chat
function parseMarkdown(text) {
    let html = text
        // Code blocks
        .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code class="language-$1">$2</code></pre>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Headers
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        // Bold
        .replace(/\*\*([^\*]+)\*\*/g, '<strong>$1</strong>')
        // Italic
        .replace(/\*([^\*]+)\*/g, '<em>$1</em>')
        // Lists
        .replace(/^\* (.+)$/gim, '<li>$1</li>')
        .replace(/^- (.+)$/gim, '<li>$1</li>')
        .replace(/^\d+\. (.+)$/gim, '<li>$1</li>')
        // Links
        .replace(/\[([^\]]+)\]\(([^\)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

    // Wrap consecutive list items in ul
    html = html.replace(/(<li>.*<\/li>\s*)+/g, (match) => `<ul>${match}</ul>`);

    // Convert double newlines to paragraph breaks (not double <br>)
    html = html.replace(/\n\n+/g, '</p><p>');

    // Convert single newlines to single breaks (for better spacing)
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraph tags
    html = '<p>' + html + '</p>';

    // Clean up empty paragraphs
    html = html.replace(/<p>\s*<\/p>/g, '');
    html = html.replace(/<p>(<[hul])/g, '$1'); // Remove <p> before headings/lists
    html = html.replace(/(<\/[hul].*?>)<\/p>/g, '$1'); // Remove </p> after headings/lists

    return html;
}

async function playAudio(text) {
    try {
        const response = await fetch(`${API_BASE}/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.play();
    } catch (error) {
        console.error('TTS failed:', error);
    }
}

clearMemory.addEventListener('click', async () => {
    await fetch(`${API_BASE}/chat/clear`, { method: 'POST' });
    chatMessages.innerHTML = '<div class="welcome-card"><div class="welcome-icon">👋</div><h3>Memory Cleared!</h3><p>Start a new conversation</p></div>';
});

// Summarizer
document.getElementById('summarizeBtn').addEventListener('click', async () => {
    const style = document.getElementById('summaryStyle').value;
    const output = document.getElementById('summaryOutput');

    output.textContent = 'Generating summary...';

    try {
        const response = await fetch(`${API_BASE}/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ style })
        });
        const data = await response.json();
        output.innerHTML = marked(data.summary || 'No summary available');
    } catch (error) {
        output.textContent = 'Error generating summary';
    }
});

// Summarizer Reset
document.getElementById('resetSummarizerBtn')?.addEventListener('click', () => {
    document.getElementById('summaryOutput').innerHTML = '';
    // Clear document selections
    document.querySelectorAll('#summarizerDocChips .doc-chip').forEach(chip => {
        chip.classList.remove('selected');
    });
});

// Flashcards - Generate and Save
document.getElementById('flashcardsBtn').addEventListener('click', async () => {
    const output = document.getElementById('flashcardsOutput');
    output.innerHTML = 'Generating flashcards...';

    try {
        const response = await fetch(`${API_BASE}/flashcards/generate`, { method: 'POST' });
        const data = await response.json();

        if (data.cards && data.cards.length > 0) {
            output.innerHTML = data.cards.map(card => `
                <div class="flashcard" onclick="this.classList.toggle('flipped')">
                    <div class="front"><strong>Q:</strong> ${card.front}</div>
                    <div class="back"><strong>A:</strong> ${card.back}</div>
                </div>
            `).join('');

            // Show success message
            const message = document.createElement('div');
            message.style.cssText = 'margin-top: 16px; padding: 16px; background: rgba(48, 209, 88, 0.15); border: 1px solid var(--success); border-radius: 12px; color: var(--success); font-weight: 600; text-align: center;';
            message.textContent = `✓ ${data.message || 'Flashcards saved!'}`;
            output.appendChild(message);

            // Update stats
            loadFlashcardStats();
        } else {
            output.textContent = 'No flashcards generated';
        }
    } catch (error) {
        output.textContent = 'Error generating flashcards';
    }
});

// Flashcards Reset
document.getElementById('resetFlashcardsBtn')?.addEventListener('click', () => {
    document.getElementById('flashcardsOutput').innerHTML = '';
    // Clear document selections
    document.querySelectorAll('#flashcardsDocChips .doc-chip').forEach(chip => {
        chip.classList.remove('selected');
    });
});

// Mind Map & 3D Knowledge Graph
let currentVizMode = '2d';
let graph3D = null;
let graphData = null;
let physicsEnabled = true;
let selectedTopic = null;

// Step 1: Extract Topics
document.getElementById('extractTopicsBtn')?.addEventListener('click', async () => {
    const btn = document.getElementById('extractTopicsBtn');

    // Get selected documents
    const selectedDocs = getSelectedDocsForSection('mindmap');
    console.log('=== MINDMAP DOCUMENT SELECTION ===');
    console.log('Selected documents:', selectedDocs);
    console.log('Number of selected:', selectedDocs.length);

    if (selectedDocs.length === 0) {
        alert('Please select at least one document first!');
        return;
    }

    btn.textContent = '⏳ Extracting topics...';
    btn.disabled = true;

    try {
        const requestBody = { documents: selectedDocs };
        console.log('Sending to backend:', requestBody);

        const response = await fetch(`${API_BASE}/mindmap/topics`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ documents: selectedDocs })
        });
        const data = await response.json();

        if (data.topics && data.topics.length > 0) {
            // Show topic chips
            const topicChips = document.getElementById('topicChips');
            topicChips.innerHTML = data.topics.map(topic => `
                <div class="topic-chip" data-topic-name="${topic.name}" data-topic-desc="${topic.description || ''}">
                    <span class="topic-name">${topic.name}</span>
                    <span class="topic-desc">${topic.description || ''}</span>
                </div>
            `).join('');

            // Add click handlers
            topicChips.querySelectorAll('.topic-chip').forEach(chip => {
                chip.addEventListener('click', () => {
                    // Toggle selection
                    topicChips.querySelectorAll('.topic-chip').forEach(c => c.classList.remove('selected'));
                    chip.classList.add('selected');

                    selectedTopic = {
                        name: chip.dataset.topicName,
                        description: chip.dataset.topicDesc
                    };

                    // Show generate buttons
                    document.getElementById('vizModeToggle').style.display = 'flex';
                    document.getElementById('generateBtnsRow').style.display = 'flex';
                });
            });

            // Show topic selection area
            document.getElementById('topicSelectionArea').style.display = 'block';
            btn.textContent = '✅ Topics Extracted';
        } else {
            btn.textContent = '❌ No topics found';
        }
    } catch (error) {
        btn.textContent = '❌ Error extracting topics';
        console.error(error);
    }

    setTimeout(() => {
        btn.textContent = '📋 Extract Topics';
        btn.disabled = false;
    }, 2000);
});

// Mind Map Reset
document.getElementById('resetMindmapBtn')?.addEventListener('click', () => {
    document.getElementById('mindmapOutput').innerHTML = '';
    const graph3DContainer = document.getElementById('3d-graph');
    if (graph3DContainer) {
        graph3DContainer.innerHTML = '';
        graph3D = null;
        graphData = null;
    }
    const nodeDetails = document.getElementById('nodeDetails');
    if (nodeDetails) nodeDetails.style.display = 'none';

    // Reset UI
    const topicArea = document.getElementById('topicSelectionArea');
    if (topicArea) topicArea.style.display = 'none';
    const vizToggle = document.getElementById('vizModeToggle');
    if (vizToggle) vizToggle.style.display = 'none';
    const genBtns = document.getElementById('generateBtnsRow');
    if (genBtns) genBtns.style.display = 'none';
    document.querySelectorAll('.topic-chip').forEach(c => c.classList.remove('selected'));
    selectedTopic = null;

    currentVizMode = '2d';
    document.getElementById('mode2DBtn')?.classList.add('active');
    document.getElementById('mode3DBtn')?.classList.remove('active');
    document.getElementById('mindmapOutput').style.display = 'block';
    document.getElementById('knowledgeGraphContainer').style.display = 'none';
});

// Generate Mind Map for Selected Topic
document.getElementById('mindmapBtn')?.addEventListener('click', async () => {
    if (!selectedTopic) {
        alert('Please select a topic first!');
        return;
    }

    if (currentVizMode === '2d') {
        const output = document.getElementById('mindmapOutput');
        output.innerHTML = `<div style="padding: 20px; text-align: center;">🔄 Generating mind map for "${selectedTopic.name}"...</div>`;

        // Get selected documents
        const selectedDocs = getSelectedDocsForSection('mindmap');

        try {
            const response = await fetch(`${API_BASE}/mindmap/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic_name: selectedTopic.name,
                    topic_description: selectedTopic.description,
                    documents: selectedDocs
                })
            });
            const data = await response.json();

            output.innerHTML = `<div class="mermaid">${data.code}</div>`;
            mermaid.run({ nodes: output.querySelectorAll('.mermaid') });
        } catch (error) {
            output.innerHTML = `<p style="color: #FF453A;">Error: ${error.message}</p>`;
        }
    } else {
        await generate3DGraph();
    }
});

// Quiz Generator
document.getElementById('generateQuizBtn')?.addEventListener('click', async () => {
    const output = document.getElementById('quizOutput');
    const difficulty = document.getElementById('quizDifficulty').value;

    // Get selected documents
    const selectedDocs = getSelectedDocsForSection('quiz');

    // Map difficulty to question count
    const questionCounts = { 'easy': 5, 'medium': 10, 'hard': 15 };
    const numQuestions = questionCounts[difficulty] || 10;

    output.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>Generating ${numQuestions} ${difficulty} questions...</p>
            <p class="loading-hint">This may take 5-15 seconds</p>
        </div>
    `;

    try {
        const response = await fetch(`${API_BASE}/quiz`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                difficulty,
                documents: selectedDocs,
                num_questions: numQuestions
            })
        });
        const data = await response.json();

        if (data.questions && data.questions.length > 0) {
            output.innerHTML = data.questions.map((q, idx) => `
                <div class="quiz-question">
                    <h4>Question ${idx + 1}: ${q.question}</h4>
                    <div class="quiz-options">
                        ${q.options.map((opt, i) => `
                            <div class="quiz-option" data-correct="${i === q.correct}">
                                ${String.fromCharCode(65 + i)}. ${opt}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `).join('');

            // Add click handlers for options
            document.querySelectorAll('.quiz-option').forEach(option => {
                option.addEventListener('click', function () {
                    const isCorrect = this.dataset.correct === 'true';
                    const parent = this.closest('.quiz-question');

                    // Remove previous selections
                    parent.querySelectorAll('.quiz-option').forEach(opt => {
                        opt.style.background = '';
                        opt.style.borderColor = '';
                    });

                    // Show correct/incorrect
                    if (isCorrect) {
                        this.style.background = 'rgba(48, 209, 88, 0.2)';
                        this.style.borderColor = 'var(--success)';
                    } else {
                        this.style.background = 'rgba(255, 69, 58, 0.2)';
                        this.style.borderColor = '#FF453A';

                        // Also show the correct answer
                        parent.querySelectorAll('.quiz-option').forEach(opt => {
                            if (opt.dataset.correct === 'true') {
                                opt.style.background = 'rgba(48, 209, 88, 0.2)';
                                opt.style.borderColor = 'var(--success)';
                            }
                        });
                    }
                });
            });
        } else {
            output.textContent = 'No questions generated. Please upload documents first.';
        }
    } catch (error) {
        output.textContent = 'Error generating quiz';
        console.error('Quiz error:', error);
    }
});

// Quiz Reset
document.getElementById('resetQuizBtn')?.addEventListener('click', () => {
    document.getElementById('quizOutput').innerHTML = '';
    // Clear document selections
    document.querySelectorAll('#quizDocChips .doc-chip').forEach(chip => {
        chip.classList.remove('selected');
    });
});

// Mode toggle buttons
document.getElementById('mode2DBtn')?.addEventListener('click', () => {
    currentVizMode = '2d';
    document.getElementById('mode2DBtn').classList.add('active');
    document.getElementById('mode3DBtn').classList.remove('active');
    document.getElementById('mindmapOutput').style.display = 'block';
    document.getElementById('knowledgeGraphContainer').style.display = 'none';
});

document.getElementById('mode3DBtn')?.addEventListener('click', () => {
    currentVizMode = '3d';
    document.getElementById('mode3DBtn').classList.add('active');
    document.getElementById('mode2DBtn').classList.remove('active');
    document.getElementById('mindmapOutput').style.display = 'none';
    document.getElementById('knowledgeGraphContainer').style.display = 'block';

    // Prevent page zoom when scrolling on 3D container
    const graphContainer = document.getElementById('knowledgeGraphContainer');
    graphContainer.addEventListener('wheel', (e) => {
        e.preventDefault();
        e.stopPropagation();
    }, { passive: false });
});


// Generate and render 3D knowledge graph
async function generate3DGraph() {
    const container = document.getElementById('3d-graph');

    // Get selected topic and documents
    const topicName = selectedTopic?.name || 'General';
    const topicDesc = selectedTopic?.description || '';
    const selectedDocs = getSelectedDocsForSection('mindmap');

    container.innerHTML = `<div style="color:white;padding:50px;text-align:center;">🔄 Generating 3D knowledge graph for "${topicName}"...</div>`;

    try {
        // Send POST request with topic and document selection
        const response = await fetch(`${API_BASE}/knowledge-graph`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                topic_name: topicName,
                topic_description: topicDesc,
                documents: selectedDocs
            })
        });
        graphData = await response.json();

        // Clear container
        container.innerHTML = '';

        // Initialize 3D Force Graph
        graph3D = ForceGraph3D()(container)
            .graphData(graphData)
            .nodeLabel('name')
            .nodeAutoColorBy('group')
            .nodeVal(node => node.val || 10)
            .nodeOpacity(0.9)
            .linkDirectionalParticles(2)
            .linkDirectionalParticleSpeed(0.003)
            .linkWidth(link => link.value || 1)
            .linkOpacity(0.3)
            .onNodeClick(handleNodeClick)
            .onNodeHover(handleNodeHover)
            .backgroundColor('#00000000'); // Transparent to show gradient

        // Prevent page zoom when scrolling on 3D graph
        container.addEventListener('wheel', (e) => {
            e.preventDefault();
            e.stopPropagation();
        }, { passive: false });

        // Populate cluster filter
        populateClusterFilter();

    } catch (error) {
        container.innerHTML = '<div style="color:#FF453A;padding:50px;text-align:center;">Error generating knowledge graph:<br>' + error.message + '</div>';
        console.error('Error:', error);
    }
}

// Handle node click - show details panel
function handleNodeClick(node) {
    const detailsPanel = document.getElementById('nodeDetails');

    if (!node) {
        detailsPanel.style.display = 'none';
        return;
    }

    // Find connected nodes
    const connections = graphData.links.filter(link =>
        link.source.id === node.id || link.target.id === node.id
    );

    const connectedNodes = connections.map(link => {
        if (link.source.id === node.id) {
            return { node: graphData.nodes.find(n => n.id === link.target.id), type: link.type };
        } else {
            return { node: graphData.nodes.find(n => n.id === link.source.id), type: link.type };
        }
    });

    detailsPanel.innerHTML = `
        <button class="btn-close" onclick="document.getElementById('nodeDetails').style.display='none'">×</button>
        <h4>${node.name}</h4>
        <p class="node-description">${node.description || 'No description available'}</p>
        <div class="node-connections">
            <h5>Connected Concepts (${connectedNodes.length})</h5>
            <ul class="connection-list">
                ${connectedNodes.map(c => `
                    <li class="connection-item">
                        ${c.node ? c.node.name : 'Unknown'}
                        <div class="connection-type">${c.type.replace(/_/g, ' ')}</div>
                    </li>
                `).join('')}
            </ul>
        </div>
    `;

    detailsPanel.style.display = 'block';
}

// Handle node hover - highlight connections
function handleNodeHover(node) {
    // Highlight connected nodes/links
    if (graph3D) {
        if (node) {
            const connectedNodeIds = new Set();
            graphData.links.forEach(link => {
                if (link.source.id === node.id) connectedNodeIds.add(link.target.id);
                if (link.target.id === node.id) connectedNodeIds.add(link.source.id);
            });

            // Dim non-connected nodes
            graph3D.nodeOpacity(n =>
                n === node || connectedNodeIds.has(n.id) ? 0.9 : 0.2
            );
            graph3D.linkOpacity(link =>
                link.source.id === node.id || link.target.id === node.id ? 0.6 : 0.1
            );
        } else {
            // Reset opacity
            graph3D.nodeOpacity(0.9);
            graph3D.linkOpacity(0.3);
        }
    }
}

// Reset camera view
document.getElementById('resetCamera')?.addEventListener('click', () => {
    if (graph3D) {
        graph3D.cameraPosition({ x: 0, y: 0, z: 1000 }, { x: 0, y: 0, z: 0 }, 1000);
    }
});

// Toggle physics simulation
document.getElementById('togglePhysics')?.addEventListener('click', (e) => {
    if (graph3D) {
        physicsEnabled = !physicsEnabled;
        if (physicsEnabled) {
            graph3D.d3Force('charge').strength(-120);
            e.target.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg> Pause';
        } else {
            graph3D.d3Force('charge').strength(0);
            e.target.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Resume';
        }
    }
});

// Search nodes
let searchTimeout;
document.getElementById('searchNode')?.addEventListener('input', (e) => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        const query = e.target.value.toLowerCase();

        if (!query || !graph3D) {
            // Reset highlight
            graph3D?.nodeOpacity(0.9).linkOpacity(0.3);
            return;
        }

        const matchedNodes = graphData.nodes.filter(n =>
            n.name.toLowerCase().includes(query) ||
            (n.description && n.description.toLowerCase().includes(query))
        );

        if (matchedNodes.length > 0) {
            const matchedIds = new Set(matchedNodes.map(n => n.id));

            // Highlight matched nodes
            graph3D.nodeOpacity(n => matchedIds.has(n.id) ? 1.0 : 0.2);
            graph3D.linkOpacity(link =>
                matchedIds.has(link.source.id) || matchedIds.has(link.target.id) ? 0.5 : 0.1
            );

            // Focus on first match
            const firstMatch = matchedNodes[0];
            if (firstMatch) {
                graph3D.cameraPosition(
                    { x: firstMatch.x, y: firstMatch.y, z: firstMatch.z + 200 },
                    firstMatch,
                    1000
                );
            }
        }
    }, 300);
});

// Populate cluster filter dropdown
function populateClusterFilter() {
    if (!graphData) return;

    const groups = [...new Set(graphData.nodes.map(n => n.group))];
    const select = document.getElementById('clusterFilter');

    // Clear existing options except "All Topics"
    select.innerHTML = '<option value="all">All Topics</option>';

    // Add cluster options
    groups.forEach(group => {
        const option = document.createElement('option');
        option.value = group;
        option.textContent = `Topic ${group}`;
        select.appendChild(option);
    });
}

// Filter by cluster
document.getElementById('clusterFilter')?.addEventListener('change', (e) => {
    if (!graph3D || !graphData) return;

    const selectedGroup = e.target.value;

    if (selectedGroup === 'all') {
        // Show all nodes
        graph3D.nodeOpacity(0.9).linkOpacity(0.3);
    } else {
        // Show only selected cluster
        const groupNum = parseInt(selectedGroup);
        graph3D.nodeOpacity(n => n.group === groupNum ? 0.9 : 0.1);
        graph3D.linkOpacity(link =>
            link.source.group === groupNum && link.target.group === groupNum ? 0.5 : 0.05
        );
    }
});

// Quiz
document.getElementById('quizBtn').addEventListener('click', async () => {
    const output = document.getElementById('quizOutput');
    output.innerHTML = 'Generating quiz...';

    try {
        const response = await fetch(`${API_BASE}/quiz`, { method: 'POST' });
        const data = await response.json();

        if (data.quiz && Array.isArray(data.quiz)) {
            output.innerHTML = data.quiz.map((q, i) => `
                <div class="quiz-question">
                    <h4>Question ${i + 1}: ${q.question}</h4>
                    <div class="quiz-options">
                        ${q.options.map(opt => `
                            <div class="quiz-option">${opt}</div>
                        `).join('')}
                    </div>
                    <details style="margin-top: 16px;">
                        <summary style="cursor: pointer; color: var(--accent); font-weight: 600;">Show Answer</summary>
                        <p style="margin-top: 12px;"><strong>Correct:</strong> ${q.answer}</p>
                        <p>${q.explanation || ''}</p>
                    </details>
                </div>
            `).join('');
        } else {
            output.textContent = 'No quiz generated';
        }
    } catch (error) {
        output.textContent = 'Error generating quiz';
    }
});

// Simple markdown parser for summaries
function marked(text) {
    let html = text
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/^[\-\*] (.+)$/gim, '<li>$1</li>')
        .replace(/^\d+\. (.+)$/gim, '<li>$1</li>')
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    // Wrap consecutive <li> in <ul>
    html = html.replace(/(<li>.*?<\/li>(?:\s*<li>.*?<\/li>)*)/gs, '<ul>$1</ul>');

    // Wrap paragraphs
    if (!html.startsWith('<h') && !html.startsWith('<ul')) {
        html = '<p>' + html + '</p>';
    }

    return html;
}

/* ===== Flashcard Review System ===== */

// Global state for review session
let reviewCards = [];
let currentCardIndex = 0;
let sessionStats = { again: 0, hard: 0, good: 0, easy: 0 };

// Load flashcard statistics
async function loadFlashcardStats() {
    // Show loading state
    const dueMessage = document.getElementById('dueMessage');
    if (dueMessage) dueMessage.textContent = 'Loading...';

    try {
        // Add timeout for slow connections
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        const response = await fetch(`${API_BASE}/flashcards/stats`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        const stats = await response.json();

        document.getElementById('totalCards').textContent = stats.total_cards || 0;
        document.getElementById('dueCards').textContent = stats.due_cards || 0;
        document.getElementById('reviewsToday').textContent = stats.reviews_today || 0;
        document.getElementById('totalReviews').textContent = stats.total_reviews || 0;

        // Update sidebar badge
        const badge = document.getElementById('dueBadge');
        if (stats.due_cards > 0) {
            badge.textContent = stats.due_cards;
            badge.style.display = 'inline-block';
        } else {
            badge.style.display = 'none';
        }

        // Update due message
        const startBtn = document.getElementById('startReviewBtn');

        if (stats.due_cards > 0) {
            dueMessage.textContent = `You have ${stats.due_cards} card${stats.due_cards > 1 ? 's' : ''} to review`;
            startBtn.style.display = 'inline-block';
        } else {
            dueMessage.textContent = 'No cards due for review. Great job!';
            startBtn.style.display = 'none';
        }
    } catch (error) {
        console.error('Error loading stats:', error);
        if (dueMessage) {
            dueMessage.textContent = error.name === 'AbortError'
                ? 'Loading timed out. Click to retry.'
                : 'Error loading stats.';
        }
    }
}

// Load due flashcards
async function loadDueFlashcards() {
    try {
        const response = await fetch(`${API_BASE}/flashcards/due`);
        const data = await response.json();
        reviewCards = data.cards || [];
        return reviewCards;
    } catch (error) {
        console.error('Error loading due flashcards:', error);
        return [];
    }
}

// Start review session
async function startReview() {
    // Show loading state
    const startBtn = document.getElementById('startReviewBtn');
    const originalText = startBtn.textContent;
    startBtn.textContent = 'Loading cards...';
    startBtn.disabled = true;

    const cards = await loadDueFlashcards();

    if (cards.length === 0) {
        startBtn.textContent = originalText;
        startBtn.disabled = false;
        return;
    }

    reviewCards = cards;
    currentCardIndex = 0;
    sessionStats = { again: 0, hard: 0, good: 0, easy: 0 };

    // Hide start screen, show session
    document.getElementById('reviewStart').style.display = 'none';
    document.getElementById('reviewSession').style.display = 'block';
    document.getElementById('reviewComplete').style.display = 'none';

    // Reset button
    startBtn.textContent = originalText;
    startBtn.disabled = false;

    showCard(0);
}

// Show a flashcard
function showCard(index) {
    if (index >= reviewCards.length) {
        // Session complete
        showSessionComplete();
        return;
    }

    const card = reviewCards[index];

    // Reset card flip
    document.getElementById('cardInner').classList.remove('flipped');

    // Set card content
    document.querySelector('#cardFront .card-content').textContent = card.front;
    document.querySelector('#cardBack .card-content').textContent = card.back;

    // Update progress
    const progress = ((index) / reviewCards.length) * 100;
    document.getElementById('progressFill').style.width = `${progress}%`;
    document.getElementById('progressText').textContent = `${index} / ${reviewCards.length}`;

    // Show "Show Answer" button, hide quality buttons
    document.getElementById('showAnswerBtn').style.display = 'inline-block';
    document.getElementById('qualityButtons').style.display = 'none';
}

// Flip card to show answer
document.getElementById('showAnswerBtn')?.addEventListener('click', () => {
    document.getElementById('cardInner').classList.add('flipped');
    document.getElementById('showAnswerBtn').style.display = 'none';
    document.getElementById('qualityButtons').style.display = 'grid';
});

// Handle quality rating
document.querySelectorAll('.btn-quality').forEach(btn => {
    btn.addEventListener('click', async () => {
        const quality = btn.dataset.quality;
        const card = reviewCards[currentCardIndex];

        // Track stats
        sessionStats[quality]++;

        // Submit review
        try {
            await fetch(`${API_BASE}/flashcards/review`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    flashcard_id: card.id,
                    quality: quality
                })
            });

            // Move to next card
            currentCardIndex++;
            showCard(currentCardIndex);

        } catch (error) {
            console.error('Error submitting review:', error);
        }
    });
});

// Show session complete
function showSessionComplete() {
    document.getElementById('reviewSession').style.display = 'none';
    document.getElementById('reviewComplete').style.display = 'block';

    // Update progress to 100%
    document.getElementById('progressFill').style.width = '100%';
    document.getElementById('progressText').textContent = `${reviewCards.length} / ${reviewCards.length}`;

    // Show stats
    const statsHtml = `
        <p style="margin: 8px 0;"><strong style="color: #FF453A;">Again:</strong> ${sessionStats.again}</p>
        <p style="margin: 8px 0;"><strong style="color: var(--warning);">Hard:</strong> ${sessionStats.hard}</p>
        <p style="margin: 8px 0;"><strong style="color: var(--success);">Good:</strong> ${sessionStats.good}</p>
        <p style="margin: 8px 0;"><strong style="color: var(--accent);">Easy:</strong> ${sessionStats.easy}</p>
    `;
    document.getElementById('completeStats').innerHTML = statsHtml;

    const reviewedCount = reviewCards.length;
    document.getElementById('completeMessage').textContent =
        `You reviewed ${reviewedCount} card${reviewedCount > 1 ? 's' : ''}!`;
}

// Finish review and return to start
document.getElementById('finishReviewBtn')?.addEventListener('click', () => {
    document.getElementById('reviewComplete').style.display = 'none';
    document.getElementById('reviewStart').style.display = 'block';

    // Reload stats
    loadFlashcardStats();
});

// Start review button
document.getElementById('startReviewBtn')?.addEventListener('click', startReview);

// Load stats when Review tab is opened
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        if (item.dataset.tab === 'review') {
            loadFlashcardStats();
        }
    });
});

// Clear all flashcards
document.getElementById('clearAllCardsBtn')?.addEventListener('click', async () => {
    const confirmed = confirm('Are you sure you want to delete ALL flashcards? This cannot be undone.');

    if (!confirmed) return;

    const btn = document.getElementById('clearAllCardsBtn');
    btn.textContent = '🗑️ Deleting...';
    btn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/flashcards/clear`, {
            method: 'DELETE'
        });
        const data = await response.json();

        // Show success message
        alert(data.message || 'All flashcards deleted!');

        // Reload stats
        loadFlashcardStats();
    } catch (error) {
        console.error('Error clearing flashcards:', error);
        alert('Error deleting flashcards');
    } finally {
        btn.textContent = '🗑️ Clear All Cards';
        btn.disabled = false;
    }
});

// Initial load
loadFlashcardStats();
