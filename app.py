from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from openai import OpenAI
import os
import uuid
from datetime import datetime, timedelta
import redis
from rq import Queue
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client

from models import db, Contact, Conversation, Message, AnalyticsEvent, KnowledgeBaseArticle, Integration

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'gold-luxury-secret-key-2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')
redis_conn = redis.from_url(redis_url)
task_queue = Queue(connection=redis_conn)

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60)
client = OpenAI()
twilio_client = None

with app.app_context():
    db.create_all()

def send_proactive_messages():
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(minutes=2)
        old_convs = Conversation.query.filter(Conversation.started_at < cutoff, Conversation.status == 'open').all()
        for conv in old_convs:
            last_msg = Message.query.filter_by(conversation_id=conv.id).order_by(Message.timestamp.desc()).first()
            if last_msg and last_msg.role == 'user' and (datetime.utcnow() - last_msg.timestamp).seconds > 120:
                proactive_msg = "Hi! Is there anything else I can help you with? 😊"
                ai_msg = Message(conversation_id=conv.id, role='bot', content=proactive_msg)
                db.session.add(ai_msg)
                db.session.commit()
                if conv.channel == 'whatsapp' and conv.contact.phone:
                    global twilio_client
                    if twilio_client is None:
                        twilio_client = Client(os.environ.get('TWILIO_ACCOUNT_SID'), os.environ.get('TWILIO_AUTH_TOKEN'))
                    twilio_client.messages.create(
                        body=proactive_msg,
                        from_=os.environ.get('TWILIO_WHATSAPP_NUMBER'),
                        to=f'whatsapp:{conv.contact.phone}'
                    )

scheduler.add_job(func=send_proactive_messages, trigger="interval", seconds=60)

def trigger_webhooks(event_type, data):
    webhooks = Integration.query.filter_by(type='webhook').all()
    for wh in webhooks:
        import requests
        try:
            requests.post(wh.config['url'], json={'event': event_type, 'data': data})
        except:
            pass

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
        
        contact = Contact.query.filter_by(email=user_id).first()
        if not contact:
            contact = Contact(name='Guest', email=user_id)
            db.session.add(contact)
            db.session.commit()
            trigger_webhooks('contact.created', {'id': contact.id, 'email': contact.email})
        
        conv = Conversation.query.filter_by(contact_id=contact.id, status='open').first()
        if not conv:
            conv = Conversation(contact_id=contact.id, channel='web')
            db.session.add(conv)
            db.session.commit()
        
        user_msg = Message(conversation_id=conv.id, role='user', content=message)
        db.session.add(user_msg)
        db.session.commit()
        
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': message}]
        )
        reply = response.choices[0].message.content
        
        ai_msg = Message(conversation_id=conv.id, role='assistant', content=reply)
        db.session.add(ai_msg)
        db.session.commit()
        
        event = AnalyticsEvent(event_type='message_sent', user_id=user_id, properties={'role': 'user'})
        db.session.add(event)
        db.session.commit()
        
        return jsonify({'success': True, 'reply': reply, 'timestamp': datetime.now().isoformat()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/history/<user_id>')
def get_history(user_id):
    try:
        contact = Contact.query.filter_by(email=user_id).first()
        if not contact:
            return jsonify({'success': True, 'history': []})
        conv = Conversation.query.filter_by(contact_id=contact.id).order_by(Conversation.started_at.desc()).first()
        if not conv:
            return jsonify({'success': True, 'history': []})
        messages = Message.query.filter_by(conversation_id=conv.id).order_by(Message.timestamp).all()
        history = [{'role': m.role, 'content': m.content, 'timestamp': m.timestamp.isoformat()} for m in messages if m.role != 'bot']
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/summary')
def analytics_summary():
    total_messages = Message.query.count()
    total_conversations = Conversation.query.count()
    total_contacts = Contact.query.count()
    return jsonify({
        'success': True,
        'data': {
            'messages': total_messages,
            'conversations': total_conversations,
            'contacts': total_contacts
        }
    })

@app.route('/api/analytics/events')
def analytics_events():
    events = AnalyticsEvent.query.order_by(AnalyticsEvent.timestamp.desc()).limit(50).all()
    return jsonify({
        'success': True,
        'events': [{'type': e.event_type, 'timestamp': e.timestamp.isoformat()} for e in events]
    })

@app.route('/api/kb/articles')
def get_articles():
    articles = KnowledgeBaseArticle.query.all()
    return jsonify({'success': True, 'articles': [{'id': a.id, 'title': a.title} for a in articles]})

@app.route('/api/kb/search')
def search_kb():
    q = request.args.get('q', '')
    articles = KnowledgeBaseArticle.query.filter(
        KnowledgeBaseArticle.title.contains(q) | KnowledgeBaseArticle.content.contains(q)
    ).all()
    return jsonify({'success': True, 'articles': [{'id': a.id, 'title': a.title, 'content': a.content[:200]} for a in articles]})

@app.route('/api/kb/article/<int:id>')
def get_article(id):
    article = KnowledgeBaseArticle.query.get_or_404(id)
    article.views += 1
    db.session.commit()
    return jsonify({'success': True, 'article': {'title': article.title, 'content': article.content}})

@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    incoming_msg = request.values.get('Body', '').strip()
    sender = request.values.get('From', '')
    phone = sender.replace('whatsapp:', '')
    
    contact = Contact.query.filter_by(phone=phone).first()
    if not contact:
        contact = Contact(name='WhatsApp User', phone=phone)
        db.session.add(contact)
        db.session.commit()
        trigger_webhooks('contact.created', {'id': contact.id, 'phone': contact.phone})
    
    conv = Conversation.query.filter_by(contact_id=contact.id, status='open', channel='whatsapp').first()
    if not conv:
        conv = Conversation(contact_id=contact.id, channel='whatsapp')
        db.session.add(conv)
        db.session.commit()
    
    msg = Message(conversation_id=conv.id, role='user', content=incoming_msg)
    db.session.add(msg)
    db.session.commit()
    
    try:
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': incoming_msg}]
        )
        reply = response.choices[0].message.content
    except Exception as e:
        reply = f"Error: {str(e)}"
    
    ai_msg = Message(conversation_id=conv.id, role='assistant', content=reply)
    db.session.add(ai_msg)
    db.session.commit()
    
    twiml_resp = MessagingResponse()
    twiml_resp.message(reply)
    return str(twiml_resp), 200

@app.route('/admin')
def admin_dashboard():
    return render_template('admin.html')

@app.route('/api/webhook/incoming', methods=['POST'])
def incoming_webhook():
    data = request.json
    return jsonify({'success': True}), 200

@socketio.on('message')
def handle_message(data):
    try:
        user_id = data.get('user_id')
        message = data.get('message')
        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[{'role': 'user', 'content': message}]
        )
        emit('response', {
            'reply': response.choices[0].message.content,
            'timestamp': datetime.now().isoformat()
        }, room=user_id)
    except Exception as e:
        emit('response', {'reply': f'Error: {str(e)}', 'timestamp': datetime.now().isoformat()}, room=user_id)

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id', str(uuid.uuid4()))
    session['user_id'] = user_id
    emit('connected', {'user_id': user_id})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
    if __name__ == "__main__":
    app.run()
