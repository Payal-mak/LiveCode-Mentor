# 🎓 LiveCode Mentor

[![VS Code Marketplace](https://img.shields.io/visual-studio-marketplace/v/payal-mak.livecode-mentor)](https://marketplace.visualstudio.com/items?itemName=payal-mak.livecode-mentor)

> An AI-powered VSCode extension that acts as a real-time coding tutor for beginner programmers — explaining code, detecting mistakes, visualizing execution, and adapting to your learning level as you type.

---

## 📌 Problem Statement

Beginner programmers often struggle to understand the logic and behavior of the code they write. While writing code, students don't fully understand what's happening — they copy snippets, do trial-and-error debugging, and constantly switch between their IDE and external tools like ChatGPT or StackOverflow.

**The core problems:**
- No real-time explanation of what code actually does
- Error messages are too technical for beginners
- Learning and coding happen as separate, disconnected activities
- Constant context-switching breaks the coding flow
- No personalized guidance based on what the user already knows

**LiveCode Mentor solves this** by integrating an AI tutor directly inside VSCode — explaining your code as you type, detecting mistakes before they become bugs, and adapting its explanations based on your learning history.

---

## ✨ Features

## 🛠️ Tech Stack

```
┌─────────────────────────────────────────────────────┐
│                   VSCode Extension                   │
│              TypeScript + VSCode API                 │
│           WebView Sidebar (HTML/CSS/JS)              │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP (axios)
                      ▼
┌─────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│                    Python 3.11                       │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ AST      │  │ Tracer   │  │  Groq AI         │  │
│  │ Parser   │  │ sys.     │  │  llama-3.3-70b   │  │
│  │          │  │ settrace │  │                  │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│                                                      │
│  ┌─────────────────────────────────────────────┐    │
│  │           SQLite Database                   │    │
│  │  concept_history | mistake_history |        │    │
│  │  session_logs                               │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

| Layer | Technology |
|---|---|
| IDE Extension | TypeScript, VSCode Extension API |
| Frontend | WebView HTML/CSS/JS |
| Backend | Python FastAPI |
| AI | Groq API (llama-3.3-70b-versatile) |
| Code Analysis | Python AST, sys.settrace |
| Database | SQLite (stdlib) |
| Visualization | Mermaid.js |
| HTTP Client | Axios |
| Packaging | vsce |

---

## 🚀 Setup Instructions

### Prerequisites

Make sure you have these installed:

```bash
node --version    # v18 or higher
python --version  # v3.10 or higher
git --version
```

### 1. Clone the Repository

```bash
git clone https://github.com/Payal-mak/LiveCode-Mentor.git
cd LiveCode-Mentor/livecode-mentor
```

### 2. Backend Setup (Python + FastAPI)

```bash
# Navigate to backend folder
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "GROQ_API_KEY=your_groq_api_key_here" > .env
```

**Get your free Groq API key:**
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up with Google
3. Click API Keys → Create API Key
4. Copy the key (starts with `gsk_...`)

**Start the backend:**
```bash
uvicorn main:app --reload --port 8000
```

You should see:
```
[LiveCode Mentor] Database initialized ✅
INFO: Application startup complete.
```

Verify at: `http://localhost:8000/health`

### 3. Extension Setup (VSCode)

Open a **new terminal** (keep backend running):

```bash
# From livecode-mentor root folder
cd ..   # if you're in backend/
npm install
npm run compile
```

You should see:
```
[watch] build finished
```

**Run the extension:**
1. Open the `livecode-mentor` folder in VSCode
2. Press **F5** (or Run → Start Debugging)
3. Select **Run Extension**
4. A second VSCode window opens — this is the **Extension Development Host**

### 4. Test the Extension

In the Extension Development Host window:
1. Open or create any `.py` file
2. Click the **🎓 LiveCode Mentor icon** in the left activity bar
3. Start typing Python code
4. Watch the Explain tab update in real time!

---

## 🏗️ Architecture Overview

```
User types code in VSCode
         │
         ▼
VSCode Extension (TypeScript)
  ├── onDidChangeTextDocument → debounce 1.5s → /analyze
  ├── onDidSaveTextDocument → /analyze + /auto-test
  └── WebviewViewProvider → renders sidebar HTML
         │
         ▼
FastAPI Backend (Python)
  │
  ├── /analyze
  │     ├── check_syntax() → AST parse → SyntaxError?
  │     │     └── YES → get_friendly_error() → Groq
  │     ├── detect_concepts() → AST visitor → concept set
  │     ├── detect_mistakes() → AST visitor → mistake patterns
  │     ├── get_experience_level() → SQLite query
  │     ├── get_explanation() → Groq (adaptive by level + mode)
  │     └── save_concepts() + save_mistake() → SQLite
  │
  ├── /hint → Groq (hint without solution)
  ├── /check-fix → detect_mistakes() again
  ├── /flow → Groq (Mermaid.js syntax)
  ├── /trace → sys.settrace() + mock input()
  ├── /auto-test → AST analysis + Groq + trace_code()
  ├── /recommendations → AST fingerprint + Groq
  ├── /explain-line → Groq (line-specific explanation)
  └── /stats → SQLite aggregation
         │
         ▼
WebView Sidebar
  ├── 💡 Explain Tab
  │     ├── What your code does (adaptive)
  │     ├── Level badge (🌱 Beginner / ⚡ Intermediate / 🚀 Expert)
  │     ├── ⚡ Complexity Analysis (Time + Space)
  │     ├── 🧠 Concepts Detected (pills)
  │     ├── ⚠️ Error Found (red card)
  │     ├── 🔍 Line Explanation (click-to-explain)
  │     ├── 📚 Recommended Resources (LeetCode + articles)
  │     └── 🧪 Auto Test Results
  ├── 🔍 Hint Tab
  │     ├── Hint card (no solutions, just guidance)
  │     └── ✅ Check My Fix button
  ├── 🔀 Flow Tab
  │     ├── Generate Flow Diagram (Mermaid)
  │     └── Step Through Code (variable stepper)
  └── 📊 Progress Tab
        ├── Top concepts bar chart
        ├── Mistakes detected / fixed
        └── Session timer
```

---

## 📸 Screenshots

| Tab | Screenshot |
|---|---|
| Explain Tab (Learning Mode) | <img width="997" height="894" alt="image" src="https://github.com/user-attachments/assets/f94f56cd-28c3-4ce4-8e09-2e0345e9f413" />
` |
| Explain Tab (Developer Mode) | <img width="1017" height="732" alt="image" src="https://github.com/user-attachments/assets/046d0d2b-3281-4a90-b4a5-300b9437f085" />
` |
| Hint Tab (mistake detected) | <img width="984" height="681" alt="image" src="https://github.com/user-attachments/assets/bbac4655-6c50-4b58-9dc7-1f9293905711" />
` |
| Flow Tab (flow diagram) | <img width="1057" height="734" alt="image" src="https://github.com/user-attachments/assets/3bab70bd-1c0c-42cf-bb1e-a7d053dc9ea6" />
` |
| Flow Tab (step through) | <img width="900" height="661" alt="image" src="https://github.com/user-attachments/assets/fc3a4dcd-ee6f-439d-b4b8-eeec0642ecf1" />
` |
| Progress Tab | <img width="928" height="945" alt="image" src="https://github.com/user-attachments/assets/3a5140df-a44b-435a-841f-751c6906bf94" />
` |

---

## 👩‍💻 Author

**Payal Makwana**

---

This project was built as part of the Human-Centered Design course.

---
