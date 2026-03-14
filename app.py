from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from openai import OpenAI
import os
import uuid
from datetime import datetime
import base64
import mimetypes

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gold-luxury-secret-key-2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize SocketIO with CORS
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60)

# Initialize OpenAI
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Store chat history (in production use Redis/MongoDB)
chat_sessions = {}
user_profiles = {}

# System prompt for luxury AI
SYSTEM_PROMPT = """You are a luxury AI concierge for a premium SaaS platform. 
Your responses should be:
- Extremely polite and professional
- Use elegant language
- Offer personalized assistance
- Be helpful and concise
- Use emojis occasionally for warmth (✨, 👑, 💫)
- Address user as "Sir/Ma'am" or by name if known"""

@app.route('/')
def home():
    # Generate unique user ID if not exists
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template('index.html', user_id=session['user_id'])

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_id = data.get('user_id', session.get('user_id', 'anonymous'))
        message = data.get('message')
        
        # Initialize session for new user
        if user_id not in chat_sessions:
            chat_sessions[user_id] = []
            chat_sessions[user_id].append({
                'role': 'system',
                'content': SYSTEM_PROMPT
            })
        
        # Add user message
        chat_sessions[user_id].append({
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Get AI response
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=chat_sessions[user_id],
            temperature=0.7,
            max_tokens=500
        )
        
        reply = response.choices[0].message.content
        
        # Add AI response
        chat_sessions[user_id].append({
            'role': 'assistant',
            'content': reply,
            'timestamp': datetime.now().isoformat()
        })
        
        # Keep only last 50 messages
        if len(chat_sessions[user_id]) > 50:
            chat_sessions[user_id] = chat_sessions[user_id][-50:]
        
        return jsonify({
            'success': True,
            'reply': reply,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_file():
    try:
        data = request.json
        file_data = data.get('file')
        file_name = data.get('fileName')
        file_type = data.get('fileType')
        user_id = data.get('user_id')
        
        # In production, save to cloud storage (S3, etc.)
        # Here we just return success
        
        return jsonify({
            'success': True,
            'message': f'File {file_name} uploaded successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/<user_id>')
def get_history(user_id):
    try:
        history = chat_sessions.get(user_id, [])
        # Remove system messages from history sent to client
        client_history = [msg for msg in history if msg['role'] != 'system']
        return jsonify({'success': True, 'history': client_history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/user/profile', methods=['POST'])
def update_profile():
    try:
        data = request.json
        user_id = data.get('user_id')
        name = data.get('name')
        email = data.get('email')
        
        user_profiles[user_id] = {
            'name': name,
            'email': email,
            'updated_at': datetime.now().isoformat()
        }
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# WebSocket events
@socketio.on('typing')
def handle_typing(data):
    user_id = data.get('user_id')
    is_typing = data.get('typing')
    emit('user_typing', {'user_id': user_id, 'typing': is_typing}, broadcast=True)

@socketio.on('message')
def handle_message(data):
    user_id = data.get('user_id')
    message = data.get('message')
    
    # Get AI response
    response = client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[{'role': 'user', 'content': message}]
    )
    
    emit('response', {
        'reply': response.choices[0].message.content,
        'timestamp': datetime.now().isoformat()
    }, room=user_id)

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id', str(uuid.uuid4()))
    session['user_id'] = user_id
    emit('connected', {'user_id': user_id})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
