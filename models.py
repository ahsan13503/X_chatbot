from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Contact(db.Model):
    __tablename__ = "contacts"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True)
    phone = db.Column(db.String(20))
    custom_fields = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    conversations = db.relationship(
        "Conversation", backref="contact", lazy=True, cascade="all, delete-orphan"
    )


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey("contacts.id"))
    status = db.Column(db.String(20), default="open")
    channel = db.Column(db.String(20), default="web")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    messages = db.relationship(
        "Message", backref="conversation", lazy=True, cascade="all, delete-orphan"
    )


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"))
    role = db.Column(db.String(20))
    content = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class AnalyticsEvent(db.Model):
    __tablename__ = "analytics_events"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50))
    user_id = db.Column(db.String(100))
    properties = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class KnowledgeBaseArticle(db.Model):
    __tablename__ = "kb_articles"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    tags = db.Column(db.Text)
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Integration(db.Model):
    __tablename__ = "integrations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    type = db.Column(db.String(50))
    config = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
