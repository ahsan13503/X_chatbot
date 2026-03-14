from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import openai
import os
import uuid
from datetime import datetime

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gold-luxury-secret-key-2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60)

# OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")

chat_sessions = {}

SYSTEM_PROMPT = """You are a luxury AI concierge for a premium SaaS platform.
Your responses should be:
- Extremely polite and professional
- Use elegant language
- Offer personalized assistance
- Be helpful and concise
- Use emojis occasionally for warmth (✨, 👑, 💫)
- Address user as "Sir/Ma'am" or by name if known
"""

@app.route('/')
def home():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    return render_template('index.html', user_id=session['user_id'])

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_id = data.get('user_id', session.get('user_id', 'anonymous'))
        message = data.get('message')

        if user_id not in chat_sessions:
            chat_sessions[user_id] = []
            chat_sessions[user_id].append({'role': 'system', 'content': SYSTEM_PROMPT})

        chat_sessions[user_id].append({'role': 'user', 'content': message})

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=chat_sessions[user_id],
            temperature=0.7,
            max_tokens=500
        )

        reply = response["choices"][0]["message"]["content"]

        chat_sessions[user_id].append({'role': 'assistant', 'content': reply})

        return jsonify({
            'success': True,
            'reply': reply,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/history/<user_id>')
def get_history(user_id):
    try:
        history = chat_sessions.get(user_id, [])
        client_history = [msg for msg in history if msg['role'] != 'system']
        return jsonify({'success': True, 'history': client_history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@socketio.on('message')
def handle_message(data):
    try:
        message = data.get('message')

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{'role': 'user', 'content': message}]
        )

        emit('response', {
            'reply': response["choices"][0]["message"]["content"],
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        emit('response', {
            'reply': f'Error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        })


@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id', str(uuid.uuid4()))
    session['user_id'] = user_id
    emit('connected', {'user_id': user_id})


if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
