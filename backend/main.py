import os
from datetime import datetime, timedelta
from typing import Optional

import requests
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker


# =========================================================
# ENV / CONFIG
# =========================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chatbot.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter")  # openrouter or rule-based
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

app = FastAPI(title="ADHD Happiness SaaS Chatbot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    preferred_tone = Column(String(50), default="calm")
    created_at = Column(DateTime, default=datetime.utcnow)

    chats = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    moods = relationship("MoodLog", back_populates="user", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chats")


class MoodLog(Base):
    __tablename__ = "mood_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    mood_value = Column(Integer, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="moods")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    done = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tasks")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================================================
# SCHEMAS
# =========================================================

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    preferred_tone: Optional[str] = None


class ChatRequest(BaseModel):
    message: str


class MoodCreate(BaseModel):
    mood_value: Optional[int] = None
    note: Optional[str] = None


class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


# =========================================================
# AUTH HELPERS
# =========================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if len(plain_password.encode("utf-8")) > 72:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long")
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise credentials_exception
    return user


# =========================================================
# AI HELPERS
# =========================================================

def build_history_messages(history: list[ChatMessage]) -> list[dict]:
    messages = []
    for item in history[-6:]:
        role = "assistant" if item.role == "assistant" else "user"
        messages.append({
            "role": role,
            "content": item.content
        })
    return messages


def call_openrouter(user_message: str, history: list[ChatMessage], tone: str = "calm") -> str:
    messages = [
        {
            "role": "system",
            "content": (
                f"You are a supportive ADHD-friendly chatbot. "
                f"Tone: {tone}. "
                f"Be calm, practical, concise, and helpful. "
                f"Help with mood, focus, routines, and starting tasks. "
                f"Do not diagnose mental illness. "
                f"Do not give medical advice. "
                f"Do not repeat the same generic line. "
                f"Give a useful response based on the user's actual message."
            )
        },
        *build_history_messages(history),
        {
            "role": "user",
            "content": user_message
        }
    ]

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": messages,
        },
        timeout=60,
    )

    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def rule_based_reply(user_message: str) -> str:
    msg = user_message.lower()

    if any(x in msg for x in ["mood", "sad", "low", "not ok", "bad day", "upset"]):
        return "I’m sorry today feels heavy. Tell me what feels hardest right now, and we’ll make it smaller."

    if any(x in msg for x in ["focus", "concentrate", "study", "attention", "distracted"]):
        return "Let’s reduce the pressure. Pick one thing and work on it for just 5 minutes."

    if any(x in msg for x in ["routine", "schedule", "habit"]):
        return "A simple routine can help: one small task, one short break, then repeat."

    if any(x in msg for x in ["task", "start", "overwhelmed", "procrastinating"]):
        return "Let’s break it down. What is the smallest possible first step?"

    return "I’m here with you. Tell me whether you want help with mood, focus, routine, or starting a task."


# =========================================================
# BASIC ROUTES
# =========================================================

@app.get("/")
def root():
    return {"status": "ok", "message": "ADHD SaaS chatbot backend running"}


@app.get("/config")
def config():
    return {
        "mode": AI_PROVIDER,
        "model": OPENROUTER_MODEL if AI_PROVIDER == "openrouter" else "rule-based"
    }


# =========================================================
# AUTH ROUTES
# =========================================================

@app.post("/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=payload.name.strip(),
        email=payload.email.lower().strip(),
        hashed_password=get_password_hash(payload.password),
        preferred_tone="calm",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Account created successfully",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "preferred_tone": user.preferred_tone,
        },
    }


@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = form_data.username.lower().strip()
    password = form_data.password

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    access_token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "preferred_tone": user.preferred_tone,
        },
    }


@app.get("/auth/me")
def auth_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "preferred_tone": current_user.preferred_tone,
    }


# =========================================================
# PROFILE ROUTES
# =========================================================

@app.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "preferred_tone": current_user.preferred_tone,
    }


@app.get("/profile/{user_id}")
def get_profile_by_id(user_id: str, current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "preferred_tone": current_user.preferred_tone,
    }


@app.put("/profile")
def update_profile(payload: ProfileUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if payload.name is not None:
        current_user.name = payload.name.strip()
    if payload.preferred_tone is not None:
        current_user.preferred_tone = payload.preferred_tone.strip()

    db.commit()
    db.refresh(current_user)

    return {
        "message": "Profile updated",
        "profile": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "preferred_tone": current_user.preferred_tone,
        },
    }


# =========================================================
# MOOD ROUTES
# =========================================================

@app.post("/mood")
def create_mood(payload: MoodCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mood = MoodLog(
        user_id=current_user.id,
        mood_value=payload.mood_value,
        note=payload.note,
    )
    db.add(mood)
    db.commit()
    db.refresh(mood)

    return {
        "message": "Mood saved",
        "mood": {
            "id": mood.id,
            "mood_value": mood.mood_value,
            "note": mood.note,
            "created_at": mood.created_at,
        },
    }


@app.get("/mood")
def get_latest_mood(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mood = (
        db.query(MoodLog)
        .filter(MoodLog.user_id == current_user.id)
        .order_by(desc(MoodLog.created_at))
        .first()
    )

    if not mood:
        return {"mood": None}

    return {
        "mood": {
            "id": mood.id,
            "mood_value": mood.mood_value,
            "note": mood.note,
            "created_at": mood.created_at,
        }
    }


@app.get("/mood/{user_id}")
def get_latest_mood_by_id(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    mood = (
        db.query(MoodLog)
        .filter(MoodLog.user_id == current_user.id)
        .order_by(desc(MoodLog.created_at))
        .first()
    )

    if not mood:
        return {"mood": None}

    return {
        "mood": {
            "id": mood.id,
            "mood_value": mood.mood_value,
            "note": mood.note,
            "created_at": mood.created_at,
        }
    }


# =========================================================
# TASK ROUTES
# =========================================================

@app.post("/tasks")
def create_task(payload: TaskCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = Task(user_id=current_user.id, title=payload.title.strip(), done=False)
    db.add(task)
    db.commit()
    db.refresh(task)

    return {
        "message": "Task created",
        "task": {
            "id": task.id,
            "title": task.title,
            "done": task.done,
            "created_at": task.created_at,
        },
    }


@app.get("/tasks")
def get_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .order_by(desc(Task.created_at))
        .all()
    )

    return {
        "tasks": [
            {"id": t.id, "title": t.title, "done": t.done, "created_at": t.created_at}
            for t in tasks
        ]
    }


@app.get("/tasks/{user_id}")
def get_tasks_by_id(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    tasks = (
        db.query(Task)
        .filter(Task.user_id == current_user.id)
        .order_by(desc(Task.created_at))
        .all()
    )

    return {
        "tasks": [
            {"id": t.id, "title": t.title, "done": t.done, "created_at": t.created_at}
            for t in tasks
        ]
    }


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.done is not None:
        task.done = payload.done

    db.commit()
    db.refresh(task)

    return {
        "message": "Task updated",
        "task": {"id": task.id, "title": task.title, "done": task.done}
    }


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}


# =========================================================
# CHAT ROUTES
# =========================================================

@app.get("/chat/history")
def chat_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return {
        "history": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "created_at": item.created_at,
            }
            for item in items
        ]
    }


@app.get("/history/{user_id}")
def history_by_id(user_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    items = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    return {
        "history": [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "created_at": item.created_at,
            }
            for item in items
        ]
    }


@app.post("/chat")
def chat(req: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    message = req.message.strip()
    if not message:
        return {
            "reply": "Send me a message and I’ll help with one small step.",
            "response": "Send me a message and I’ll help with one small step.",
            "mode": "fallback",
        }

    user_msg = ChatMessage(user_id=current_user.id, role="user", content=message)
    db.add(user_msg)
    db.commit()

    recent_history = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    if AI_PROVIDER == "openrouter":
        try:
            reply = call_openrouter(message, recent_history, current_user.preferred_tone)
            mode = "openrouter"
            model = OPENROUTER_MODEL
        except Exception as e:
            reply = rule_based_reply(message)
            mode = "fallback"
            model = None

            assistant_msg = ChatMessage(user_id=current_user.id, role="assistant", content=reply)
            db.add(assistant_msg)
            db.commit()

            return {
                "reply": reply,
                "response": reply,
                "mode": mode,
                "model": model,
                "error": str(e),
            }
    else:
        reply = rule_based_reply(message)
        mode = "rule-based"
        model = "rule-based"

    assistant_msg = ChatMessage(user_id=current_user.id, role="assistant", content=reply)
    db.add(assistant_msg)
    db.commit()

    return {
        "reply": reply,
        "response": reply,
        "mode": mode,
        "model": model,
    }
