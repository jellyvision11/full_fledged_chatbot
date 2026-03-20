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

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });

  const [config, setConfig] = useState(null);
  const [history, setHistory] = useState([]);
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

  async function loadHistory() {
    try {
      const res = await apiGet('/chat/history');
      setHistory(res?.history || []);
    } catch (err) {
      console.error('loadHistory error:', err);
      setHistory([]);
    }
  }

  async function boot() {
    setBootLoading(true);
    await loadConfig();

    if (token) {
      await loadHistory();
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
    setHistory([]);
    setMessage('');
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
        {
          role: 'assistant',
          content: 'Something went wrong while sending the message.',
        },
      ]);
    }
  }

  if (!token) {
    return <AuthPage onLogin={handleLogin} />;
  }

  if (bootLoading) {
    return (
      <div className="app-shell">
        <div className="chat-wrapper">
          <div className="chat-card">
            <h2>Loading...</h2>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <div className="top-right-bar">
        <span className="mode-pill">
          {config?.mode || 'unknown'} · {config?.model || 'unknown'}
        </span>
        <button className="logout-btn" onClick={logout}>
          Logout
        </button>
      </div>

      <div className="chat-wrapper">
        <div className="chat-card">
          <h1>ADHD Happiness Chatbot</h1>
          <p className="subtitle">
            Your calm, practical AI companion for mood, focus, and routines.
          </p>

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

          <p className="welcome-line">
            Welcome back, {user?.name || 'User'}
          </p>
        </div>
      </div>
    </div>
  );
}