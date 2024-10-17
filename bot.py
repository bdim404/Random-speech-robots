from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from db import get_session, User, GroupMessage, RecentChatLog
from dotenv import load_dotenv
import asyncio, logging, os, requests, random, json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

API_URL = "https://www.gptapi.us/v1/chat/completions"

# Load the environment variables;
logging.info("Loading the environment variables...")
os.environ.clear()  
load_dotenv()  
try:
    API_KEY = os.getenv("OPENAI_API_KEY")
except:
    logging.error("The OPENAI_API_KEY environment variable is not set.")
    exit(1)
try:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
except:
    logging.error("The TELEGRAM_BOT_TOKEN environment variable is not set.")
    exit(1)
logging.info("Environment variables loaded.")

async def process_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    logging.info(f"Processing message from {user_id}.")
    session = get_session()

    # Get the user's chat history;
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        user = User(id=user_id, most_frequent_messages=json.dumps({}), recent_messages='', top_emojis='')
        session.add(user)

    # Check if the message is a sticker;
    if update.message.sticker:
        sticker = update.message.sticker
        logging.info(f"{user} - Sticker sent - File ID: {sticker.file_id}")

        # Update the user's most frequent stickers;
        sticker_data = json.loads(user.top_emojis) if user.top_emojis else {}
        sticker_data[sticker.file_id] = sticker_data.get(sticker.file_id, 0) + 1
        user.top_emojis = json.dumps(sticker_data)

    # Handled the text message;
    if update.message.text:
        message_content = update.message.text
        logging.info(f"{user} - Text message received: {message_content}")

        # Update the user's most frequent messages;
        freq_data = json.loads(user.most_frequent_messages) if user.most_frequent_messages else {}
        freq_data[message_content] = freq_data.get(message_content, 0) + 1

        # Checke if the message is the top 20 most frequent;
        if len(freq_data) > 20:
            # Sorted the messages by their frequency;
            sorted_freq_data = sorted(freq_data.items(), key=lambda x: x[1], reverse=True)
            freq_data = dict(sorted_freq_data[:20])  

        user.most_frequent_messages = json.dumps(freq_data)

        # Update 30 messages for user;
        recent_messages = user.recent_messages.split('\n') if user.recent_messages else []
        if len(recent_messages) >= 30:
            recent_messages.pop(0)
        recent_messages.append(message_content)
        user.recent_messages = '\n'.join(recent_messages)

        # Recorde the group messages;
        group_message = GroupMessage(user_id=user_id, content=message_content)
        session.add(group_message)

        # Update the gruop's most frequent messages;
        recent_chat_log = session.query(RecentChatLog).order_by(RecentChatLog.createdAt.desc()).limit(50).all()
        if len(recent_chat_log) >= 50:
            oldest = session.query(RecentChatLog).order_by(RecentChatLog.createdAt.asc()).first()
            session.delete(oldest)
        session.add(RecentChatLog(content=message_content))
    else:
        logging.info("No text message received")
        


    # Random Trigger Response;
    if random.random() < 1:  # 5% chance to trigger response;
        await trigger_openai_response(session, update)

    session.commit()

async def trigger_openai_response(session, update: Update) -> None:
    user = session.query(User).order_by(User.id).first()
    recent_chat_log = session.query(RecentChatLog).order_by(RecentChatLog.createdAt.desc()).limit(50).all()

    # Handle the group message formats
    group_chat_context = "\n".join([msg.content for msg in reversed(recent_chat_log)])

    # Handle the most frequest messages;
    most_frequent_messages = json.loads(user.most_frequent_messages)
    formatted_messages = [f"{msg}: {count}次" for msg, count in most_frequent_messages.items()]
    formatted_messages_str = "\n".join(formatted_messages)

    content = f"请根据'{user.id}' 发言习惯:“\n{formatted_messages_str}”\n 以及他的最近发言:\n“{user.recent_messages}”\n来参与群聊的其中一个话题:\n{group_chat_context}\n ，注意，群聊信息可能包含多个话题，根据以上信息生成一条以愤怒/愉悦/调侃等某种语气的简短回复。如果群聊出现了多条相同的内容，那你可以选择当复读机。"
    
    logging.info(f"触发 OpenAI 响应, 发送内容为 {content}")
    # Call OpenAI to get the generated message;
    messages = [
        {"role": "system", "content": "你是一个模仿人说话的大师,能在简短的聊天记录中学习到某人发言的习惯。"},
        {"role": "user", "content": content}
    ]
    
    bot_response = await connectOpenAi(messages)

    # 随机决定发送文本还是贴纸
    if random.random() < 0.9:  # 30% 概率发送贴纸
        sticker_data = json.loads(user.top_emojis) if user.top_emojis else {}
        if sticker_data:
            selected_sticker_file_id = random.choice(list(sticker_data.keys()))
            await update.message.reply_sticker(selected_sticker_file_id)
        else:
            await update.message.reply_text(bot_response)
    else:
        await update.message.reply_text(bot_response)

async def connectOpenAi(messages):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-3.5-turbo",
        "messages": messages
    }

    for attempt in range(2):
        try:
            response = requests.post(API_URL, headers=headers, data=json.dumps(data))

            if response.status_code == 200:
                response_json = response.json()
                bot_message = response_json['choices'][0]['message']['content']
                return bot_message
            else:
                logging.error(f"API request failed with status code: {response.status_code}, response: {response.text}")
        except Exception as e:
            logging.error(f"API request failed, retrying... Attempt {attempt + 1}. Error: {str(e)}")
    logging.error("Failed after 2 retries.")
    return "API error!"


app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.ALL, process_message))
app.run_polling()
