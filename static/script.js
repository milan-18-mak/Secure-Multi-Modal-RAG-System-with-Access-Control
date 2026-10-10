const API_BASE = '/api';

let currentUser = null;
let token = null;

const loginModal = document.getElementById('login-modal');
const loginForm = document.getElementById('login-form');
const logoutBtn = document.getElementById('logout-btn');
const userDisplay = document.getElementById('user-display');
const chatForm = document.getElementById('chat-form');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const sourcesList = document.getElementById('sources-list');
const authInfo = document.getElementById('auth-info');

document.addEventListener('DOMContentLoaded', () => {
    const savedToken = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');
    
    if (savedToken && savedUser) {
        token = savedToken;
        currentUser = JSON.parse(savedUser);
        updateUIForLoggedInUser();
        fetchAuthInfo();
    } else {
        showLoginModal();
    }
    
    loginForm.addEventListener('submit', handleLogin);
    logoutBtn.addEventListener('click', handleLogout);
    chatForm.addEventListener('submit', handleChat);
});

function showLoginModal() {
    loginModal.classList.remove('hidden');
    messageInput.disabled = true;
    sendBtn.disabled = true;
}

function hideLoginModal() {
    loginModal.classList.add('hidden');
}

function updateUIForLoggedInUser() {
    hideLoginModal();
    userDisplay.textContent = `Logged in as: ${currentUser.username} (${currentUser.role})`;
    logoutBtn.style.display = 'block';
    messageInput.disabled = false;
    sendBtn.disabled = false;
    addSystemMessage(`Welcome, ${currentUser.username}! You can now ask questions.`);
}

function handleLogin(e) {
    e.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    fetch(`${API_BASE}/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
            username: username,
            password: password
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => Promise.reject(err));
        }
        return response.json();
    })
    .then(data => {
        token = data.access_token;
        currentUser = {
            user_id: data.user_id,
            username: data.username,
            role: data.role
        };
        localStorage.setItem('token', token);
        localStorage.setItem('user', JSON.stringify(currentUser));
        updateUIForLoggedInUser();
        fetchAuthInfo();
        loginForm.reset();
    })
    .catch(error => {
        alert(error.detail || 'Login failed');
    });
}

function handleLogout() {
    token = null;
    currentUser = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    userDisplay.textContent = 'Not logged in';
    logoutBtn.style.display = 'none';
    messageInput.disabled = true;
    sendBtn.disabled = true;
    chatMessages.innerHTML = '';
    sourcesList.innerHTML = '<p class="empty-state">No sources retrieved yet</p>';
    authInfo.innerHTML = '<p class="empty-state">Log in to see authorization info</p>';
    showLoginModal();
}

async function handleChat(e) {
    e.preventDefault();
    
    const message = messageInput.value.trim();
    if (!message) return;
    
    addUserMessage(message);
    messageInput.value = '';
    sendBtn.disabled = true;
    messageInput.disabled = true;
    
    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ message })
        });
        
        if (!response.ok) {
            throw new Error('Failed to get response');
        }
        
        const data = await response.json();
        addAssistantMessage(data.answer, data.citations);
        updateSourcesPanel(data.retrieved_sources);
    } catch (error) {
        addSystemMessage('Error: ' + error.message);
    } finally {
        sendBtn.disabled = false;
        messageInput.disabled = false;
        messageInput.focus();
    }
}

function addUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message user';
    div.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(div);
    scrollToBottom();
}

function addAssistantMessage(text, citations) {
    const div = document.createElement('div');
    div.className = 'message assistant';
    
    let citationHtml = '';
    if (citations && citations.length > 0) {
        citationHtml = '<div class="citations">';
        citations.forEach(cite => {
            let citeText = `Source: ${cite.source}`;
            if (cite.page) citeText += `, Page ${cite.page}`;
            if (cite.row_id) citeText += `, Row ${cite.row_id}`;
            citationHtml += `<span class="citation">${escapeHtml(citeText)}</span>`;
        });
        citationHtml += '</div>';
    }
    
    div.innerHTML = `<div class="message-content">${escapeHtml(text)}${citationHtml}</div>`;
    chatMessages.appendChild(div);
    scrollToBottom();
}

function addSystemMessage(text) {
    const div = document.createElement('div');
    div.className = 'message system';
    div.innerHTML = `<div class="message-content">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(div);
    scrollToBottom();
}

function updateSourcesPanel(sources) {
    if (!sources || sources.length === 0) {
        sourcesList.innerHTML = '<p class="empty-state">No authorized sources found</p>';
        return;
    }
    
    sourcesList.innerHTML = sources.map(source => {
        let details = '';
        if (source.page) details += `Page ${source.page}`;
        if (source.row_id) details += `${details ? ' • ' : ''}Row ${source.row_id}`;
        if (source.access_groups && source.access_groups.length) {
            details += `${details ? ' • ' : ''}Access: ${source.access_groups.join(', ')}`;
        }
        
        return `
            <div class="source-item">
                <div class="source-header">
                    <span class="source-name">${escapeHtml(source.source)}</span>
                    <span class="source-type">${escapeHtml(source.source_type)}</span>
                </div>
                <div class="source-details">${escapeHtml(details)}</div>
            </div>
        `;
    }).join('');
}

async function fetchAuthInfo() {
    try {
        const response = await fetch(`${API_BASE}/user/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (!response.ok) throw new Error('Failed to fetch auth info');
        
        const data = await response.json();
        renderAuthInfo(data);
    } catch (error) {
        authInfo.innerHTML = '<p class="empty-state">Failed to load authorization info</p>';
    }
}

function renderAuthInfo(data) {
    const allowedHtml = data.allowed_groups.map(g => 
        `<span class="auth-group allowed">✓ ${escapeHtml(g)}</span>`
    ).join(' ');
    
    const blockedHtml = data.blocked_groups.map(g => 
        `<span class="auth-group blocked">✗ ${escapeHtml(g)}</span>`
    ).join(' ');
    
    authInfo.innerHTML = `
        <div class="auth-info-item">
            <h3>User</h3>
            <div>${escapeHtml(data.username)} (${escapeHtml(data.role)})</div>
        </div>
        <div class="auth-info-item">
            <h3>Allowed</h3>
            <div>${allowedHtml || '<span class="empty-state">None</span>'}</div>
        </div>
        <div class="auth-info-item">
            <h3>Blocked</h3>
            <div>${blockedHtml || '<span class="empty-state">None</span>'}</div>
        </div>
    `;
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}