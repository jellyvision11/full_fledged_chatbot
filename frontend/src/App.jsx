import React, { useEffect, useState } from 'react';
import { apiGet, apiPatch, apiPost, apiPut, login, register } from './services/api';

const tabs = ['dashboard', 'chat', 'moods', 'tasks', 'profile'];

function AuthScreen({ onAuth }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      if (mode === 'register') {
        await register(form.name, form.email, form.password);
      }
      const data = await login(form.email, form.password);
      localStorage.setItem('token', data.access_token);
      onAuth();
    } catch (err) {
      setError('Could not authenticate. Check your details and try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <h1>ADHD Happiness Chatbot</h1>
        <p>Your calm, practical AI companion for mood, focus, and routines.</p>
        <form onSubmit={handleSubmit}>
          {mode === 'register' && (
            <input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} required />
          )}
          <input placeholder="Email" type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} required />
          <input placeholder="Password" type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })} required />
          <button disabled={loading}>{loading ? 'Please wait...' : mode === 'login' ? 'Login' : 'Create account'}</button>
        </form>
        {error && <div className="error">{error}</div>}
        <div className="switcher">
          {mode === 'login' ? 'New here?' : 'Already have an account?'}{' '}
          <span onClick={() => setMode(mode === 'login' ? 'register' : 'login')}>
            {mode === 'login' ? 'Create one' : 'Login'}
          </span>
        </div>
      </div>
    </div>
  );
}

function Dashboard({ config, moods, tasks, profile }) {
  const openTasks = tasks.filter(t => t.status !== 'done').length;
  const latestMood = moods[0];
  return (
    <div className="grid">
      <div className="card hero-card">
        <h2>Welcome back, {profile?.name || 'friend'}</h2>
        <p>Mode: {config?.mode || 'offline'} · Model: {config?.model || 'llama3.2'}</p>
        <p>{profile?.goals}</p>
      </div>
      <div className="card"><h3>Latest mood</h3><p>{latestMood ? `${latestMood.score}/10 · ${latestMood.energy}` : 'No mood logged yet'}</p></div>
      <div className="card"><h3>Open tasks</h3><p>{openTasks}</p></div>
      <div className="card"><h3>Preferred tone</h3><p>{profile?.preferred_tone || 'calm'}</p></div>
    </div>
  );
}

function ChatPage({ history, reloadHistory }) {
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);

  async function sendMessage(e) {
    e.preventDefault();
    if (!message.trim()) return;
    setSending(true);
    try {
      await apiPost('/chat', { message }, true);
      setMessage('');
      await reloadHistory();
    } catch {
      alert('Chat failed. Make sure backend and Ollama are running.');
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="card chat-card">
      <div className="chat-window">
        {history.length === 0 ? <p className="muted">No messages yet.</p> : history.map((m, i) => (
          <div key={i} className={`bubble ${m.role}`}>
            <strong>{m.role === 'user' ? 'You' : 'Bot'}</strong>
            <div>{m.content}</div>
          </div>
        ))}
      </div>
      <form className="chat-form" onSubmit={sendMessage}>
        <input value={message} onChange={e => setMessage(e.target.value)} placeholder="Tell me what feels hard right now..." />
        <button disabled={sending}>{sending ? 'Sending...' : 'Send'}</button>
      </form>
    </div>
  );
}

function MoodPage({ moods, reloadMoods }) {
  const [score, setScore] = useState(5);
  const [energy, setEnergy] = useState('medium');
  const [note, setNote] = useState('');

  async function saveMood(e) {
    e.preventDefault();
    await apiPost('/moods', { score: Number(score), energy, note });
    setNote('');
    reloadMoods();
  }

  return (
    <div className="grid">
      <div className="card">
        <h3>Log mood</h3>
        <form onSubmit={saveMood}>
          <label>Mood score</label>
          <input type="number" min="1" max="10" value={score} onChange={e => setScore(e.target.value)} />
          <label>Energy</label>
          <select value={energy} onChange={e => setEnergy(e.target.value)}>
            <option>low</option>
            <option>medium</option>
            <option>high</option>
          </select>
          <label>Note</label>
          <textarea value={note} onChange={e => setNote(e.target.value)} placeholder="What shaped your mood today?" />
          <button>Save mood</button>
        </form>
      </div>
      <div className="card">
        <h3>Recent entries</h3>
        <div className="list">
          {moods.map(m => (
            <div className="list-item" key={m.id}>
              <div><strong>{m.score}/10</strong> · {m.energy}</div>
              <div className="muted small">{new Date(m.created_at).toLocaleString()}</div>
              <div>{m.note}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TasksPage({ tasks, reloadTasks }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('medium');

  async function addTask(e) {
    e.preventDefault();
    await apiPost('/tasks', { title, description, priority });
    setTitle('');
    setDescription('');
    reloadTasks();
  }

  async function markDone(id) {
    await apiPatch(`/tasks/${id}`, { status: 'done' });
    reloadTasks();
  }

  return (
    <div className="grid">
      <div className="card">
        <h3>Add task</h3>
        <form onSubmit={addTask}>
          <input placeholder="Task title" value={title} onChange={e => setTitle(e.target.value)} required />
          <textarea placeholder="Description" value={description} onChange={e => setDescription(e.target.value)} />
          <select value={priority} onChange={e => setPriority(e.target.value)}>
            <option>low</option>
            <option>medium</option>
            <option>high</option>
          </select>
          <button>Add task</button>
        </form>
      </div>
      <div className="card">
        <h3>Task list</h3>
        <div className="list">
          {tasks.map(t => (
            <div className="list-item" key={t.id}>
              <div className="task-row">
                <div>
                  <strong>{t.title}</strong>
                  <div className="muted small">{t.priority} · {t.status}</div>
                  <div>{t.description}</div>
                </div>
                {t.status !== 'done' && <button className="small-btn" onClick={() => markDone(t.id)}>Done</button>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function ProfilePage({ profile, reloadProfile }) {
  const [form, setForm] = useState(profile);
  useEffect(() => setForm(profile), [profile]);
  if (!form) return null;

  async function save(e) {
    e.preventDefault();
    await apiPut('/profile', {
      preferred_tone: form.preferred_tone,
      goals: form.goals,
      struggles: form.struggles,
    });
    reloadProfile();
    alert('Profile saved');
  }

  return (
    <div className="card">
      <h3>Profile settings</h3>
      <form onSubmit={save}>
        <label>Name</label>
        <input value={form.name || ''} disabled />
        <label>Preferred tone</label>
        <select value={form.preferred_tone} onChange={e => setForm({ ...form, preferred_tone: e.target.value })}>
          <option>calm</option>
          <option>direct</option>
          <option>encouraging</option>
        </select>
        <label>Goals</label>
        <textarea value={form.goals} onChange={e => setForm({ ...form, goals: e.target.value })} />
        <label>Struggles</label>
        <textarea value={form.struggles} onChange={e => setForm({ ...form, struggles: e.target.value })} />
        <button>Save profile</button>
      </form>
    </div>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(!!localStorage.getItem('token'));
  const [tab, setTab] = useState('dashboard');
  const [config, setConfig] = useState(null);
  const [profile, setProfile] = useState(null);
  const [history, setHistory] = useState([]);
  const [moods, setMoods] = useState([]);
  const [tasks, setTasks] = useState([]);

  async function loadAll() {
    try {
      const [configData, me, profileData, historyData, moodsData, tasksData] = await Promise.all([
        apiGet('/config', false),
        apiGet('/auth/me'),
        apiGet('/profile'),
        apiGet('/chat/history'),
        apiGet('/moods'),
        apiGet('/tasks'),
      ]);
      setConfig(configData);
      setProfile({ ...profileData, name: me.name, email: me.email });
      setHistory(historyData.history);
      setMoods(moodsData.moods);
      setTasks(tasksData.tasks);
    } catch {
      localStorage.removeItem('token');
      setAuthenticated(false);
    }
  }

  useEffect(() => {
    if (authenticated) loadAll();
  }, [authenticated]);

  if (!authenticated) return <AuthScreen onAuth={() => setAuthenticated(true)} />;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div>
          <h2>ADHD Bot</h2>
          <p className="muted">SaaS-style local AI assistant</p>
        </div>
        <nav>
          {tabs.map(t => (
            <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </nav>
        <button className="logout" onClick={() => { localStorage.removeItem('token'); setAuthenticated(false); }}>Logout</button>
      </aside>
      <main className="main-content">
        <header className="topbar">
          <div>
            <h1>{tab[0].toUpperCase() + tab.slice(1)}</h1>
            <p className="muted">{config?.mode || 'offline-ollama'} · {config?.model || 'llama3.2'}</p>
          </div>
        </header>
        {tab === 'dashboard' && <Dashboard config={config} moods={moods} tasks={tasks} profile={profile} />}
        {tab === 'chat' && <ChatPage history={history} reloadHistory={async () => setHistory((await apiGet('/chat/history')).history)} />}
        {tab === 'moods' && <MoodPage moods={moods} reloadMoods={async () => setMoods((await apiGet('/moods')).moods)} />}
        {tab === 'tasks' && <TasksPage tasks={tasks} reloadTasks={async () => setTasks((await apiGet('/tasks')).tasks)} />}
        {tab === 'profile' && <ProfilePage profile={profile} reloadProfile={async () => {
          const me = await apiGet('/auth/me');
          const p = await apiGet('/profile');
          setProfile({ ...p, name: me.name, email: me.email });
        }} />}
      </main>
    </div>
  );
}
