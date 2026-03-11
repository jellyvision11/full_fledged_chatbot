from datetime import datetime, timedelta
from typing import Optional, List

import requests
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

# ---------- Config ----------
DATABASE_URL = "sqlite:///./chatbot.db"
SECRET_KEY = "change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2"

# ---------- App ----------
app = FastAPI(title="ADHD Happiness SaaS Chatbot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Database ----------
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(200), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("Profile", back_populates="user", uselist=False)
    messages = relationship("Message", back_populates="user")
    moods = relationship("Mood", back_populates="user")
    tasks = relationship("Task", back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    preferred_tone = Column(String(50), default="calm")
    goals = Column(Text, default="Reduce overwhelm, build routines, and start tasks more easily")
    struggles = Column(Text, default="Procrastination, task paralysis, and inconsistency")

    user = relationship("User", back_populates="profile")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="messages")


class Mood(Base):
    __tablename__ = "moods"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    score = Column(Integer, nullable=False)
    energy = Column(String(20), nullable=False)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="moods")


class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default="todo")
    priority = Column(String(20), default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="tasks")


Base.metadata.create_all(bind=engine)


# ---------- Auth ----------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------- Schemas ----------
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    preferred_tone: str
    goals: str
    struggles: str


class ChatRequest(BaseModel):
    message: str


class MoodRequest(BaseModel):
    score: int
    energy: str
    note: str = ""


class TaskRequest(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"


class TaskUpdate(BaseModel):
    status: str


# ---------- Helpers ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    return user


CRISIS_KEYWORDS = [
    "suicide", "kill myself", "want to die", "hurt myself", "self harm", "end my life"
]


def is_crisis(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in CRISIS_KEYWORDS)


def build_prompt(user: User, profile: Profile, history: List[Message], latest_mood: Optional[Mood], message: str) -> str:
    history_text = "\n".join([f"{m.role.capitalize()}: {m.content}" for m in history[-10:]])
    mood_text = (
        f"Latest mood: {latest_mood.score}/10, energy {latest_mood.energy}, note: {latest_mood.note}"
        if latest_mood else
        "Latest mood: unknown"
    )
    return f"""
You are a supportive ADHD-friendly happiness chatbot.

User profile:
- Name: {user.name}
- Preferred tone: {profile.preferred_tone if profile else 'calm'}
- Goals: {profile.goals if profile else 'Reduce overwhelm and build routines'}
- Common struggles: {profile.struggles if profile else 'Task paralysis and inconsistency'}
- {mood_text}

Rules:
- Keep replies short, calm, practical, and kind.
- Break work into tiny steps.
- Give one clear next step when possible.
- Never diagnose or claim to be a doctor.
- If user seems in crisis, urge immediate human help.

Conversation so far:
{history_text}

User: {message}
Assistant:
""".strip()


def call_ollama(prompt: str) -> str:
    response = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "").strip()


def fallback_reply(message: str) -> str:
    text = message.lower()
    if is_crisis(text):
        return "I’m really sorry you’re going through this. Please reach out to a trusted person near you right now. You deserve immediate human support."
    if "overwhelmed" in text or "stress" in text:
        return "Let’s make this smaller. Pick one task only. Step 1: open the material. Step 2: read one heading. Step 3: write one line. Do only step 1 first."
    if "study" in text or "exam" in text:
        return "Try this mini study sprint: choose one topic, work for 10 minutes, write 3 bullet points, then take a 2-minute break."
    return "I’m here with you. Tell me whether you want help with mood, focus, routine, or starting a task."


# ---------- Routes ----------
@app.get("/")
def root():
    return {"status": "ok", "message": "ADHD SaaS chatbot backend running"}


@app.post("/auth/register", response_model=UserOut)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    profile = Profile(user_id=user.id)
    db.add(profile)
    db.commit()
    return user


@app.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return TokenResponse(access_token=access_token)


@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@app.get("/config")
def config():
    return {"mode": "offline-ollama", "model": OLLAMA_MODEL}


@app.get("/profile")
def get_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    return {
        "name": current_user.name,
        "email": current_user.email,
        "preferred_tone": profile.preferred_tone if profile else "calm",
        "goals": profile.goals if profile else "",
        "struggles": profile.struggles if profile else "",
    }


@app.put("/profile")
def update_profile(payload: ProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    if not profile:
        profile = Profile(user_id=current_user.id)
        db.add(profile)
    profile.preferred_tone = payload.preferred_tone
    profile.goals = payload.goals
    profile.struggles = payload.struggles
    db.commit()
    return {"success": True}


@app.get("/chat/history")
def chat_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    messages = (
        db.query(Message)
        .filter(Message.user_id == current_user.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return {"history": [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]}


@app.post("/chat")
def chat(payload: ChatRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    text = payload.message.strip()
    if not text:
        return {"response": "Send me a message and I’ll help with one small step.", "mode": "offline-ollama"}

    user_msg = Message(user_id=current_user.id, role="user", content=text)
    db.add(user_msg)
    db.commit()

    history = (
        db.query(Message)
        .filter(Message.user_id == current_user.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    profile = db.query(Profile).filter(Profile.user_id == current_user.id).first()
    latest_mood = (
        db.query(Mood)
        .filter(Mood.user_id == current_user.id)
        .order_by(Mood.created_at.desc())
        .first()
    )

    if is_crisis(text):
        reply = "I’m really sorry you’re going through this. Please contact a trusted person near you right now. You deserve immediate human support."
        mode = "safety"
    else:
        prompt = build_prompt(current_user, profile, history, latest_mood, text)
        try:
            reply = call_ollama(prompt)
            mode = "offline-ollama"
            if not reply:
                reply = fallback_reply(text)
                mode = "fallback"
        except Exception:
            reply = fallback_reply(text)
            mode = "fallback"

    assistant_msg = Message(user_id=current_user.id, role="assistant", content=reply)
    db.add(assistant_msg)
    db.commit()
    return {"response": reply, "mode": mode}


@app.get("/moods")
def list_moods(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    moods = db.query(Mood).filter(Mood.user_id == current_user.id).order_by(Mood.created_at.desc()).all()
    return {"moods": [
        {
            "id": m.id,
            "score": m.score,
            "energy": m.energy,
            "note": m.note,
            "created_at": m.created_at.isoformat(),
        }
        for m in moods
    ]}


@app.post("/moods")
def add_mood(payload: MoodRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    mood = Mood(user_id=current_user.id, score=payload.score, energy=payload.energy, note=payload.note)
    db.add(mood)
    db.commit()
    return {"success": True}


@app.get("/tasks")
def list_tasks(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tasks = db.query(Task).filter(Task.user_id == current_user.id).order_by(Task.created_at.desc()).all()
    return {"tasks": [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ]}


@app.post("/tasks")
def add_task(payload: TaskRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = Task(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
    )
    db.add(task)
    db.commit()
    return {"success": True}


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: TaskUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = payload.status
    db.commit()
    return {"success": True}
