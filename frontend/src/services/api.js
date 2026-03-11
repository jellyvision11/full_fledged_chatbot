const BASE_URL = 'http://127.0.0.1:8000';

function getHeaders(auth = true, isForm = false) {
  const headers = {};
  if (!isForm) headers['Content-Type'] = 'application/json';
  const token = localStorage.getItem('token');
  if (auth && token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export async function apiGet(path, auth = true) {
  const res = await fetch(`${BASE_URL}${path}`, { headers: getHeaders(auth) });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPost(path, body, auth = true, isForm = false) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: getHeaders(auth, isForm),
    body: isForm ? body : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPut(path, body, auth = true) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PUT',
    headers: getHeaders(auth),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function apiPatch(path, body, auth = true) {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers: getHeaders(auth),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function login(email, password) {
  const form = new URLSearchParams();
  form.append('username', email);
  form.append('password', password);
  return apiPost('/auth/login', form, false, true);
}

export async function register(name, email, password) {
  return apiPost('/auth/register', { name, email, password }, false);
}
