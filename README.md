# 🎓 LiveCode Mentor

[![VS Code Marketplace](https://img.shields.io/visual-studio-marketplace/v/payal-mak.livecode-mentor?color=blue&label=VS%20Code%20Marketplace&logo=visual-studio-code)](https://marketplace.visualstudio.com/items?itemName=payal-mak.livecode-mentor)
[![Installs](https://img.shields.io/visual-studio-marketplace/i/payal-mak.livecode-mentor?color=green)](https://marketplace.visualstudio.com/items?itemName=payal-mak.livecode-mentor)
[![Rating](https://img.shields.io/visual-studio-marketplace/r/payal-mak.livecode-mentor)](https://marketplace.visualstudio.com/items?itemName=payal-mak.livecode-mentor)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **AI-powered coding tutor inside VS Code** — real-time explanations, error detection, execution tracing, and personalized learning for beginner programmers.

---

## ✨ What is LiveCode Mentor?

Beginner programmers often struggle to understand **why** their code works — not just whether it runs. LiveCode Mentor sits right inside VS Code and acts as your personal coding tutor, explaining your code as you write it, detecting mistakes before you even run it, and adapting to your skill level over time.

No more switching between your IDE, StackOverflow, and ChatGPT. Everything you need to **learn while you code** is in one place.

---

## 🚀 Features

### 🧠 Real-Time AI Explanations
Paste or write code and instantly get a plain-English explanation tailored to your experience level — beginner, intermediate, or expert. Powered by **Llama 3.3 70B via Groq API**.

### 🐛 Mistake Detection
Automatically detects common beginner errors:
- Off-by-one errors in loops
- Infinite `while True` loops with no `break`
- Mutable default arguments in functions

### 📊 Complexity Analysis
Every explanation includes **Time & Space Complexity** with Big-O notation and a plain-English reason — so you actually understand *why* it's O(n log n).

### 🔍 Deep DSA Classification
Automatically detects algorithm types: Binary Search, Dynamic Programming, Two Pointer, Graph BFS/DFS, Backtracking, Sliding Window, and 10+ more — and gives algorithm-specific explanations.

### 📈 Step-Through Execution Tracer
Watch your Python code execute **step by step** — see exactly what each variable holds at every line. Like a debugger, but explained in English.

### 🧪 Auto Test Generator
Automatically generates test cases and runs them against your code — no manual test writing needed.

### 🗺️ Flow Diagram Generator
Converts your code into a **Mermaid.js flowchart** — visualize your logic at a glance.

### 📚 Smart Recommendations
Get **LeetCode problem suggestions** and **learning articles** matched to exactly what you're practicing right now.

### 🏆 Gamification System
Earn **points and badges** as you code:
- 🐛 Bug Squasher — Fix your first bug
- 🧭 DSA Explorer — Use 3 different DSA concepts
- 💯 Century — Reach 100 points
- 🔥 On a Roll — Code 3 days in a row
- ...and more!

### 🎯 Line-by-Line Explanation
Right-click any line → **"LiveCode Mentor: Explain This Line"** — get a deep-dive explanation of exactly that line in context.

### 🔄 Adaptive Learning Mode
Switches between **Learning Mode** (beginner-friendly analogies) and **Developer Mode** (concise technical summaries) based on your preference.

---

## 📦 Installation

### From VS Code Marketplace
1. Open VS Code
2. Press `Ctrl+Shift+X` to open Extensions
3. Search for **"LiveCode Mentor"**
4. Click **Install**

### From Command Line

**Install the latest version from the marketplace:**
```bash
code --install-extension payal-mak.livecode-mentor
```

---

## 🖥️ How to Use

1. Install the extension
2. Click the **🎓 LiveCode Mentor** icon in the Activity Bar (left sidebar)
3. Open any `.py`, `.js`, `.cpp`, or `.java` file
4. Start coding — explanations appear automatically!

### Available Commands
| Command | Description |
|---|---|
| `LiveCode Mentor: Explain This Line` | Right-click any line for a deep explanation |
| `Reanalyze` | Manually trigger analysis of current file |
| `Generate Flow` | Create a flowchart of your code |
| `Set Mode` | Switch between Learning / Developer mode |

---

## 🌐 Backend & Privacy

LiveCode Mentor uses a **cloud-hosted Python backend** deployed on Render.

- **Backend URL:** `https://livecode-mentor.onrender.com`
- Your code is sent to the backend for AI analysis via the **Groq API** (Llama 3.3 70B model)
- Code is processed in real-time and **not stored permanently**
- Progress, scores, and badges are stored locally in a lightweight database

> ⚠️ **Note:** The free-tier backend may take **up to 30 seconds** to respond after a period of inactivity (Render cold start). This is normal — please wait for the first response.

### Custom Backend
If you want to run your own backend:
```bash
git clone https://github.com/Payal-mak/LiveCode-Mentor
cd LiveCode-Mentor/backend
pip install -r requirements.txt
# Add your GROQ_API_KEY to .env
uvicorn main:app --reload
```

Then update the setting in VS Code:
```
Settings → LiveCode Mentor → Backend URL → http://localhost:8000
```

---

## 🛠️ Supported Languages

| Language | Explanations | Mistake Detection | Step-Through | Auto Tests |
|---|---|---|---|---|
| Python | ✅ | ✅ | ✅ | ✅ |
| C++ | ✅ | ✅ | ❌ | ❌ |
| JavaScript | ✅ | ❌ | ❌ | ❌ |
| Java | ✅ | ❌ | ❌ | ❌ |

> Full execution features currently support Python only. C++ and JavaScript support coming soon!

---

## 🧩 Extension Settings

| Setting | Default | Description |
|---|---|---|
| `livecodeMentor.backendUrl` | `https://livecode-mentor.onrender.com` | Backend server URL |

---

## 📋 Requirements

- VS Code `^1.110.0`
- Internet connection (for AI analysis)
- No local Python installation needed!

---

## 🐞 Known Issues

- First request after inactivity may take 30–60 seconds (Render free tier cold start)
- Step-through execution only works for Python files
- Very large files (>500 lines) may have slower analysis

---

## 📝 Changelog

### 0.0.2
- Connected to cloud-hosted backend (no local setup needed)
- Fixed icon format for Marketplace compatibility
- Improved `.vscodeignore` for smaller package size

### 0.0.1
- Initial release
- Real-time AI code explanations
- Mistake detection (Python)
- Execution tracer
- Flow diagram generation
- Auto test generation
- Gamification system (badges + scores)
- LeetCode recommendations

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request at:
**[github.com/Payal-mak/LiveCode-Mentor](https://github.com/Payal-mak/LiveCode-Mentor)**

---

## 👩‍💻 Author

**Payal Makwana** — B.Tech ICT, Marwadi University

[![GitHub](https://img.shields.io/badge/GitHub-Payal--mak-black?logo=github)](https://github.com/Payal-mak)

---

## 📄 License

[MIT](LICENSE) © 2025 Payal Makwana
