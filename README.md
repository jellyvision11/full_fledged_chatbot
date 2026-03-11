# Full-fledged ADHD Happiness Chatbot

A full-stack SaaS-style chatbot with:
- FastAPI backend
- React frontend
- JWT auth
- SQLite database
- chat history
- mood tracker
- task manager
- profile settings
- local Ollama integration with fallback mode

## Run backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open frontend at:
`http://127.0.0.1:5173`

## Ollama

Install Ollama and run:

```bash
ollama run llama3.2
```

The backend calls the Ollama API on `http://localhost:11434/api/generate`.
If Ollama is unavailable, chat falls back to a simple rule-based reply.

## Default backend
Backend runs on `http://127.0.0.1:8000`
