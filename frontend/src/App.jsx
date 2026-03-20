import React, { useEffect, useState } from 'react';
import { apiGet, apiPost, login, register } from './services/api';
import './styles.css';

function AuthPage({ onLogin }) {
  const [isRegister, setIsRegister] = useState(false);
  const [name, setName] = useState('demo');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isRegister) {
        await register(name, email, password);
        setIsRegister(false);
        setError('Account created. Please login now.');
      } else {
        const data = await login(email, password);
        if (data?.access_token) {
          localStorage.setItem('token', data.access_token);
        }
        if (data?.user) {
          localStorage.setItem('user', JSON.stringify(data.user));
        }
        onLogin(data);
      }
    } catch (err) {
      setError('Could not authenticate. Check your details and try again.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app-shell auth-shell">
      <div className="auth-card">
        <h1>ADHD Happiness Chatbot</h1>
        <p>Your calm, practical AI companion for mood, focus, and routines.</p>

        <form onSubmit={handleSubmit} className="stack">
          {isRegister && (
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Name"
              required
            />
          )}

          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Email"
            type="email"
            required
          />

          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            type="password"
            required
          />

          <button type="submit" disabled={loading}>
            {loading ? 'Please wait...' : isRegister ? 'Create account' : 'Login'}
          </button>
        </form>

        {error && <p className="error-text">{error}</p>}

        <p className="switch-auth">
          {isRegister ? 'Already have an account?' : 'New here?'}{' '}
          <span onClick={() => setIsRegister((prev) => !prev)}>
            {isRegister ? 'Login' : 'Create one'}
          </span>
        </p>
      </div>
    </div>
  );
}

function DashboardCard({ title, children }) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}

function ChatPage({ history, message, setMessage, sendMessage }) {
  return (
    <div className="card">
      <h3>Chat</h3>

      <div className="chat-box">
        {(history || []).length === 0 ? (
          <div className="bot-message">
            <strong>Bot</strong>
            <p>I’m here with you. Tell me what feels hard right now.</p>
          </div>
        ) : (
          (history || []).map((item, idx) => (
            <div
              key={item.id || idx}
              className={item.role === 'user' ? 'user-message' : 'bot-message'}
            >
              <strong>{item.role === 'user' ? 'You' : 'Bot'}</strong>
              <p>{item.content}</p>
            </div>
          ))
        )}
      </div>

      <div className="chat-input-row">
        <input
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Tell me what feels hard right now..."
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              sendMessage();
            }
          }}
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}

function MoodPage({ moods, reloadMoods }) {
  const [score, setScore] = useState(5);
  const [note, setNote] = useState('');

  async function saveMood(e) {
    e.preventDefault();
    try {
      await apiPost('/mood', {
        mood_value: Number(score),
        note,
      });
      setNote('');
      reloadMoods();
    } catch (err) {
      console.error('saveMood error:', err);
      alert('Could not save mood.');
    }
  }

  const latestMood = (moods || [])[0];

  return (
    <div className="grid two-col">
      <div className="card">
        <h3>Log mood</h3>
        <form onSubmit={saveMood} className="stack">
          <input
            type="number"
            min="1"
            max="10"
            value={score}
            onChange={(e) => setScore(e.target.value)}
            placeholder="Mood 1-10"
          />
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional note"
          />
          <button type="submit">Save mood</button>
        </form>
      </div>

      <div className="card">
        <h3>Latest mood</h3>
        {latestMood ? (
          <>
            <p><strong>Score:</strong> {latestMood.mood_value ?? '-'}</p>
            <p><strong>Note:</strong> {latestMood.note || 'No note'}</p>
          </>
        ) : (
          <p>No mood logged yet</p>
        )}
      </div>
    </div>
  );
}

function TasksPage({ tasks, reloadTasks }) {
  const [title, setTitle] = useState('');

  async function createTask(e) {
    e.preventDefault();
    if (!title.trim()) return;

    try {
      await apiPost('/tasks', { title });
      setTitle('');
      reloadTasks();
    } catch (err) {
      console.error('createTask error:', err);
      alert('Could not create task.');
    }
  }

  async function toggleTask(task) {
    try {
      await fetch(
        `${'https://full-fledged-chatbot.onrender.com'}/tasks/${task.id}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${localStorage.getItem('token')}`,
          },
          body: JSON.stringify({ done: !task.done }),
        }
      );
      reloadTasks();
    } catch (err) {
      console.error('toggleTask error:', err);
    }
  }

  return (
    <div className="grid two-col">
      <div className="card">
        <h3>Create task</h3>
        <form onSubmit={createTask} className="stack">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Task title"
          />
          <button type="submit">Add task</button>
        </form>
      </div>

      <div className="card">
        <h3>Open tasks</h3>
        {(tasks || []).length === 0 ? (
          <p>No tasks yet</p>
        ) : (
          <div className="stack">
            {(tasks || []).map((task) => (
              <label key={task.id} className="task-row">
                <input
                  type="checkbox"
                  checked={!!task.done}
                  onChange={() => toggleTask(task)}
                />
                <span className={task.done ? 'done' : ''}>{task.title}</span>
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });

  const [config, setConfig] = useState(null);
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState([]);
  const [moods, setMoods] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [tab, setTab] = useState('chat');
  const [message, setMessage] = useState('');
  const [bootLoading, setBootLoading] = useState(true);

  async function loadConfig() {
    try {
      const res = await apiGet('/config', false);
      setConfig(res || null);
    } catch (err) {
      console.error('loadConfig error:', err);
      setConfig(null);
    }
  }

  async function loadProfile() {
    try {
      const res = await apiGet('/profile');
      setProfile(res || null);
    } catch (err) {
      console.error('loadProfile error:', err);
      setProfile(null);
    }
  }

  async function reloadHistory() {
    try {
      const res = await apiGet('/chat/history');
      setHistory(res?.history || []);
    } catch (err) {
      console.error('reloadHistory error:', err);
      setHistory([]);
    }
  }

  async function reloadMoods() {
    try {
      const res = await apiGet('/mood');
      if (res?.mood) {
        setMoods([res.mood]);
      } else {
        setMoods([]);
      }
    } catch (err) {
      console.error('reloadMoods error:', err);
      setMoods([]);
    }
  }

  async function reloadTasks() {
    try {
      const res = await apiGet('/tasks');
      setTasks(res?.tasks || []);
    } catch (err) {
      console.error('reloadTasks error:', err);
      setTasks([]);
    }
  }

  async function boot() {
    setBootLoading(true);
    await loadConfig();

    if (token) {
      await Promise.all([loadProfile(), reloadHistory(), reloadMoods(), reloadTasks()]);
    }

    setBootLoading(false);
  }

  useEffect(() => {
    boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function handleLogin(data) {
    setToken(localStorage.getItem('token'));
    setUser(data?.user || null);
  }

  function logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setToken(null);
    setUser(null);
    setProfile(null);
    setHistory([]);
    setMoods([]);
    setTasks([]);
  }

  async function sendMessage() {
    if (!message.trim()) return;

    const userText = message.trim();
    setMessage('');

    setHistory((prev) => [
      ...prev,
      { role: 'user', content: userText },
    ]);

    try {
      const res = await apiPost('/chat', { message: userText }, true);
      const botText = res?.reply || res?.response || 'No response received.';
      setHistory((prev) => [
        ...prev,
        { role: 'assistant', content: botText },
      ]);
    } catch (err) {
      console.error('sendMessage error:', err);
      setHistory((prev) => [
        ...prev,
        { role: 'assistant', content: 'Something went wrong while sending the message.' },
      ]);
    }
  }

  if (!token) {
    return <AuthPage onLogin={handleLogin} />;
  }

  if (bootLoading) {
    return (
      <div className="app-shell">
        <div className="card">
          <h2>Loading...</h2>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="topbar">
        <h1>Dashboard</h1>
        <button onClick={logout}>Logout</button>
      </div>

      <p className="muted">
        {config?.mode || 'unknown'} · {config?.model || 'unknown'}
      </p>

      <div className="card hero">
        <h2>Welcome back, {profile?.name || user?.name || 'User'}</h2>
        <p>
          Mode: {config?.mode || 'unknown'} · Model: {config?.model || 'unknown'}
        </p>
        <p>Reduce overwhelm, build routines, and start tasks more easily</p>
      </div>

      <div className="grid three-col">
        <DashboardCard title="Latest mood">
          {(moods || []).length > 0 ? (
            <>
              <p><strong>Score:</strong> {moods[0]?.mood_value ?? '-'}</p>
              <p>{moods[0]?.note || 'No note'}</p>
            </>
          ) : (
            <p>No mood logged yet</p>
          )}
        </DashboardCard>

        <DashboardCard title="Open tasks">
          <p>{(tasks || []).filter((t) => !t.done).length}</p>
        </DashboardCard>

        <DashboardCard title="Preferred tone">
          <p>{profile?.preferred_tone || 'calm'}</p>
        </DashboardCard>
      </div>

      <div className="tabs">
        <button onClick={() => setTab('chat')} className={tab === 'chat' ? 'active' : ''}>Chat</button>
        <button onClick={() => setTab('mood')} className={tab === 'mood' ? 'active' : ''}>Mood</button>
        <button onClick={() => setTab('tasks')} className={tab === 'tasks' ? 'active' : ''}>Tasks</button>
      </div>

      {tab === 'chat' && (
        <ChatPage
          history={history}
          message={message}
          setMessage={setMessage}
          sendMessage={sendMessage}
        />
      )}

      {tab === 'mood' && (
        <MoodPage moods={moods} reloadMoods={reloadMoods} />
      )}

      {tab === 'tasks' && (
        <TasksPage tasks={tasks} reloadTasks={reloadTasks} />
      )}
    </div>
  );
}