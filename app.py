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
CORS(app)

app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "secret-key")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*")

client = OpenAI()

redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
redis_conn = redis.from_url(redis_url)
task_queue = Queue(connection=redis_conn)

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

twilio_client = None

with app.app_context():
    db.create_all()


def send_proactive_messages():
    with app.app_context():
        cutoff = datetime.utcnow() - timedelta(minutes=2)

        old_convs = Conversation.query.filter(
            Conversation.started_at < cutoff,
            Conversation.status == "open",
        ).all()

        for conv in old_convs:
            last_msg = (
                Message.query.filter_by(conversation_id=conv.id)
                .order_by(Message.timestamp.desc())
                .first()
            )

            if last_msg and last_msg.role == "user":

                proactive_msg = "Hi! Is there anything else I can help you with?"

                ai_msg = Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=proactive_msg,
                )

                db.session.add(ai_msg)
                db.session.commit()


scheduler.add_job(func=send_proactive_messages, trigger="interval", seconds=60)


@app.route("/")
def home():
    if "user_id" not in session:
        session["user_id"] = str(uuid.uuid4())

    return render_template("index.html", user_id=session["user_id"])


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        user_id = data.get("user_id", session.get("user_id"))
        message = data.get("message")

        contact = Contact.query.filter_by(email=user_id).first()

        if not contact:
            contact = Contact(name="Guest", email=user_id)
            db.session.add(contact)
            db.session.commit()

        conv = Conversation.query.filter_by(
            contact_id=contact.id,
            status="open",
        ).first()

        if not conv:
            conv = Conversation(contact_id=contact.id, channel="web")
            db.session.add(conv)
            db.session.commit()

        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=message,
        )

        db.session.add(user_msg)
        db.session.commit()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": message}],
        )

        reply = response.choices[0].message.content

        ai_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=reply,
        )

        db.session.add(ai_msg)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "reply": reply,
                "timestamp": datetime.now().isoformat(),
            }
        )

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/history/<user_id>")
def history(user_id):

    contact = Contact.query.filter_by(email=user_id).first()

    if not contact:
        return jsonify({"history": []})

    conv = Conversation.query.filter_by(contact_id=contact.id).first()

    if not conv:
        return jsonify({"history": []})

    messages = Message.query.filter_by(conversation_id=conv.id).all()

    history = []

    for m in messages:
        history.append(
            {
                "role": m.role,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
            }
        )

    return jsonify({"history": history})


@app.route("/admin")
def admin():
    return render_template("admin.html")


@socketio.on("message")
def handle_message(data):

    user_id = data.get("user_id")
    message = data.get("message")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": message}],
    )

    emit(
        "response",
        {
            "reply": response.choices[0].message.content,
            "timestamp": datetime.now().isoformat(),
        },
        room=user_id,
    )


@socketio.on("connect")
def connect():

    user_id = session.get("user_id", str(uuid.uuid4()))
    session["user_id"] = user_id

    emit("connected", {"user_id": user_id})


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=10000)
