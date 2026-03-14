// Initialize Socket.IO
const socket = io();
let messageCount = 0;
let currentUser = '{{ user_id }}';
let typingTimer;
let isTyping = false;

// DOM Elements
const messagesContainer = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.querySelector('.send-btn');
const messageCountSpan = document.getElementById('message-count');
const sessionIdSpan = document.getElementById('session-id');

// Socket event handlers
socket.on('connect', () => {
    console.log('Connected to server');
    addActivity('Connected to server');
});

socket.on('response', (data) => {
    hideTypingIndicator();
    addMessage('assistant', data.reply, data.timestamp);
});

socket.on('user_typing', (data) => {
    if (data.user_id !== currentUser) {
        // Show other user typing
    }
});

// ========== MESSAGE FUNCTIONS ==========
async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;
    
    addMessage('user', message);
    messageInput.value = '';
    
    showTypingIndicator();
    messageCount++;
    updateStats();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                user_id: currentUser,
                message: message
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            hideTypingIndicator();
            addMessage('assistant', data.reply, data.timestamp);
            addActivity('AI responded');
        } else {
            hideTypingIndicator();
            addMessage('assistant', 'Error: Could not get response. Please try again.', new Date().toISOString());
        }
    } catch (error) {
        hideTypingIndicator();
        addMessage('assistant', 'Network error. Please check your connection.', new Date().toISOString());
    }
}

function addMessage(role, content, timestamp = new Date().toISOString()) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const time = new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${role === 'user' ? '👤' : '👑'}</div>
        <div class="message-content">
            <div class="message-sender">${role === 'user' ? 'You' : 'Luxury AI'}</div>
            <div class="message-bubble">${content}</div>
            <div class="message-time">${time}</div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    addActivity(`${role === 'user' ? 'You' : 'AI'} sent a message`);
}

function showTypingIndicator() {
    if (document.getElementById('typing-indicator')) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'message assistant';
    indicator.innerHTML = `
        <div class="message-avatar">👑</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    messagesContainer.appendChild(indicator);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    socket.emit('typing', { user_id: currentUser, typing: true });
}

function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
    socket.emit('typing', { user_id: currentUser, typing: false });
}

// Input handlers
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

messageInput.addEventListener('input', () => {
    if (!isTyping) {
        isTyping = true;
        socket.emit('typing', { user_id: currentUser, typing: true });
    }
    
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => {
        isTyping = false;
        socket.emit('typing', { user_id: currentUser, typing: false });
    }, 1000);
});

// ========== FILE UPLOAD FUNCTIONS ==========
function triggerFileUpload() {
    document.getElementById('file-input').click();
}

function uploadFile(input) {
    const file = input.files[0];
    if (!file) return;

    addMessage('user', `📎 File uploaded: ${file.name}`);

    // Simulate AI response after 1 second
    setTimeout(() => {
        addMessage('assistant', `✨ I've received your file "${file.name}". How can I help you with it?`);
    }, 1000);

    input.value = '';
}

// ========== VOICE MESSAGE FUNCTION ==========
function startVoice() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('Your browser does not support voice input. Try Chrome or Edge.');
        return;
    }

    const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = function(event) {
        const speechResult = event.results[0][0].transcript;
        document.getElementById('message-input').value = speechResult;
        // Uncomment next line to auto-send after voice
        // sendMessage();
    };

    recognition.onerror = function(event) {
        console.error('Speech recognition error', event.error);
        alert('Voice recognition error: ' + event.error);
    };

    recognition.start();
}

// ========== EMOJI PICKER ==========
function toggleEmojiPicker() {
    const picker = document.getElementById('emoji-picker');
    picker.style.display = picker.style.display === 'none' ? 'block' : 'none';
    
    if (picker.style.display === 'block') {
        const emojiPicker = document.createElement('emoji-picker');
        picker.innerHTML = '';
        picker.appendChild(emojiPicker);
        
        emojiPicker.addEventListener('emoji-click', event => {
            messageInput.value += event.detail.unicode;
            picker.style.display = 'none';
        });
    }
}

// ========== QUICK ACTIONS ==========
function quickAction(action) {
    const actions = {
        help: "I need help with the platform",
        pricing: "Tell me about your pricing plans",
        features: "What features do you offer?",
        contact: "How can I contact support?"
    };
    
    messageInput.value = actions[action];
    sendMessage();
}

// ========== PROFILE FUNCTIONS ==========
function showProfile() {
    document.getElementById('profile-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('profile-modal').style.display = 'none';
}

async function saveProfile() {
    const name = document.getElementById('profile-name').value;
    const email = document.getElementById('profile-email').value;
    
    if (name) {
        document.getElementById('user-name').textContent = name;
    }
    
    const response = await fetch('/api/user/profile', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            user_id: currentUser,
            name: name,
            email: email
        })
    });
    
    closeModal();
    addMessage('assistant', `✨ Profile updated! Welcome, ${name || 'Guest'}!`);
}

// ========== NEW CHAT ==========
function newChat() {
    messagesContainer.innerHTML = `
        <div class="message welcome-message">
            <div class="message-avatar">👑</div>
            <div class="message-content">
                <div class="message-sender">Luxury AI Concierge</div>
                <div class="message-bubble">
                    Starting a new conversation! How may I assist you today? ✨
                    <div class="message-time">Just now</div>
                </div>
            </div>
        </div>
    `;
    messageCount = 0;
    updateStats();
    addActivity('New conversation started');
}

// ========== STATISTICS ==========
function updateStats() {
    messageCountSpan.textContent = messageCount;
}

// ========== ACTIVITY ==========
function addActivity(text) {
    const activitiesList = document.getElementById('recent-activities-list');
    const activityDiv = document.createElement('div');
    activityDiv.className = 'activity-item';
    activityDiv.innerHTML = `
        <span class="activity-dot"></span>
        <span class="activity-text">${text}</span>
        <span class="activity-time">Just now</span>
    `;
    
    activitiesList.insertBefore(activityDiv, activitiesList.firstChild);
    
    while (activitiesList.children.length > 5) {
        activitiesList.removeChild(activitiesList.lastChild);
    }
}

// ========== SETTINGS ==========
function toggleSound() {
    addActivity('Sound settings toggled');
}

function toggleTheme() {
    addActivity('Theme toggled');
}

// ========== LOAD HISTORY ==========
window.onload = async function() {
    try {
        const response = await fetch(`/api/history/${currentUser}`);
        const data = await response.json();
        
        if (data.success && data.history.length > 0) {
            messagesContainer.innerHTML = '';
            data.history.forEach(msg => {
                if (msg.role !== 'system') {
                    addMessage(msg.role === 'user' ? 'user' : 'assistant', msg.content, msg.timestamp);
                }
            });
            messageCount = data.history.length;
            updateStats();
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
    
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
    });
};

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('profile-modal');
    if (event.target === modal) {
        modal.style.display = 'none';
    }
};
