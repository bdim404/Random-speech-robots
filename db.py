from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class BaseWithTimestamps:
    createdAt = Column(DateTime, default=datetime.utcnow)
    updatedAt = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class User(Base, BaseWithTimestamps):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=False)  # Telegram ID
    most_frequent_messages = Column(Text)  # Top 20 frequent messages
    recent_messages = Column(Text)  # Last 30 messages
    top_emojis = Column(Text)  # Top emojis or stickers (JSON format) used by the user

class GroupMessage(Base, BaseWithTimestamps):
    __tablename__ = 'group_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(Text)

class RecentChatLog(Base, BaseWithTimestamps):
    __tablename__ = 'recent_chat_log'
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text)  # Store last 50 messages

engine = create_engine('sqlite:///database.db', echo=False, pool_size=10, max_overflow=10)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()

Base.metadata.create_all(engine)