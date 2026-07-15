# J.A.R.V.I.S. — Voice Assistant & Dashboard

An AI-powered voice assistant built from scratch, featuring a highly-optimized Python backend that runs multiple parallel background services (Voice STT, APIs, MCP tool servers) and a clean, responsive React dashboard.

---

## 🌟 Key Features

*   **Multi-Threaded Architecture:** Running parallel daemon threads in Python to manage voice listening, WebSocket APIs, and background tasks simultaneously.
*   **Modern Web UI:** Built with **React (Vite)**, offering a sleek dashboard that displays real-time system logs, a memory browser, and modular settings.
*   **Real-time Communication:** Utilizes **WebSockets** for instant, bi-directional, low-latency communication between the Python core and the React UI.
*   **Persistent Local Memory:** Connected to a local **SQLite** database to preserve context, log memory logs, and save custom application states.
*   **Model Context Protocol (MCP):** Features custom MCP tool server integration, allowing the assistant to run system-level tasks and interact with local environments securely.
*   **Smart Configurations:** Completely modular setups managed cleanly via `.env` and `config.yaml` files.

---

## 🛠️ Technology Stack

| Component | Technologies Used |
| :--- | :--- |
| **Backend** | Python, FastAPI, WebSockets, SQLite, PyYAML, Python Threading |
| **Frontend** | React (Vite), CSS3, JavaScript (ES6+) |
| **AI & Voice** | Web Speech API, Whisper (Speech-to-Text), MCP Protocol |

---

## 📂 Project Structure

```text
├── jarvis/
│   ├── api/            # FastAPI and WebSocket implementation
│   ├── memory/         # SQLite database and memory management (jarvis.db)
│   ├── ui/             # React-based frontend dashboard
│   ├── voice/          # Whisper & voice processing configurations
│   ├── tray.py         # System tray implementation
│   └── main.py         # Primary entry point coordinating all daemon threads
├── config.yaml         # Configuration file for services
├── .env                # Environment keys and credentials (ignored in Git)
└── requirements.txt    # Backend dependencies
---

## 🚀 Setup & Installation

Follow these steps to run both backend and frontend systems locally:

### Prerequisites
* **Python 3.10+** installed.
* **Node.js** and **npm** installed.

---

### 1️⃣ Setting Up the Backend (Python)

1. **Navigate to the project root and activate the virtual environment:**
   ```bash
   # On Windows PowerShell
   .venv\Scripts\Activate.ps1
   
   # On macOS/Linux
   source .venv/bin/activate
Install all required dependencies:

Bash
pip install -r requirements.txt
Configure Environment Variables:

Create a .env file in the root folder.

Add any required API keys (such as OpenAI, Gemini, or custom tokens).

Run the JARVIS entry point:

Bash
python main.py
This starts the API server (localhost:8000), the MCP tool server (localhost:8765), and starts listening via the microphone.

2️⃣ Setting Up the Frontend (React Dashboard)
To view and interact with the JARVIS interface:

Open a new terminal window and navigate to the UI dashboard:

Bash
cd jarvis/ui/dashboard
Install dependencies:

Bash
npm install
Run the Vite development server:

Bash
npm run dev
Open the generated local link (typically http://localhost:5173) in your web browser.

🔒 Security & Best Practices
Sensitive data and personal API keys should remain strictly inside the local .env file.

The project includes a configured .gitignore that automatically prevents .env and local databases (jarvis.db) from being uploaded to GitHub.
