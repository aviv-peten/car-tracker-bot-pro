import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
from datetime import datetime, timedelta
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
START, CAR_NUMBER, PICKUP, DROPOFF, NOTE, JOB_TYPE, NEXT_OR_END = range(7)

# Data storage (in production, use a proper database)
user_data = {}
monthly_stats = defaultdict(int)

# Email configuration
EMAIL_RECIPIENTS = [
    "email1@example.com",
    "email2@example.com", 
    "email3@example.com"
]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = os.getenv('EMAIL_USER')  # Your email
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')  # Your email password or app password

# Job types in Hebrew
JOB_TYPES = [
    "משימת שינוע",
    "משימת טרמפ", 
    "משימת סרק",
    "משימת מוסך",
    "משימת טסט"
]

def load_data():
    """Load user data from file"""
    global user_data, monthly_stats
    try:
        if os.path.exists('user_data.json'):
            with open('user_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_data = data.get('user_data', {})
                monthly_stats = defaultdict(int, data.get('monthly_stats', {}))
        else:
            user_data = {}
            monthly_stats = defaultdict(int)
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        user_data = {}
        monthly_stats = defaultdict(int)

def save_data():
    """Save user data to file"""
    try:
        data = {
            'user_data': user_data,
            'monthly_stats': dict(monthly_stats)
        }
        with open('user_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def send_daily_email(daily_cars, job_stats):
    """Send daily summary via email"""
    try:
        if not EMAIL_USER or not EMAIL_PASSWORD:
            logger.warning("Email credentials not configured")
            return
            
        # Create email content
        subject = f"Daily Car Report - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"Daily Car Report - {datetime.now().strftime('%Y-%m-%d')}\n\n"
        body += f"סך כולל המשימות: {len(daily_cars)}\n"
        
        # Job type statistics
        for job_type in JOB_TYPES:
            count = job_stats.get(job_type, 0)
            body += f"{job_type}: {count}\n"
        
        body += "\nפירוט המשימות:\n"
        body += "=" * 50 + "\n\n"
        
        for i, car in enumerate(daily_cars, 1):
            body += f"משימה #{i}\n"
            body += f"מספר רכב: {car['car_number']}\n"
            body += f"מאיפה: {car['pickup']}\n"
            body += f"לאיפה: {car['dropoff']}\n"
            body += f"סוג משימה: {car['job_type']}\n"
            if car['note']:
                body += f"הערות: {car['note']}\n"
            body += f"זמן: {car['timestamp']}\n"
            body += "-" * 30 + "\n\n"
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Send to all recipients
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        
        for recipient in EMAIL_RECIPIENTS:
            msg['To'] = recipient
            text = msg.as_string()
            server.sendmail(EMAIL_USER, recipient, text)
            del msg['To']
        
        server.quit()
        logger.info("Daily email sent successfully")
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the car tracking session"""
    user_id = str(update.effective_user.id)
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {
            'daily_cars': [],
            'current_car': {}
        }
    
    # Clear current car data for new session
    user_data[user_id]['current_car'] = {}
    
    await update.message.reply_text(
        "🚗 מעקב רכבים התחיל!\n\n"
        "אנא הכנס מספר רכב:"
    )
    
    return CAR_NUMBER

async def get_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get car number from user"""
    user_id = str(update.effective_user.id)
    car_number = update.message.text.strip()
    
    user_data[user_id]['current_car']['car_number'] = car_number
    user_data[user_id]['current_car']['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    await update.message.reply_text(
        f"🚗 מספר רכב: {car_number}\n\n"
        "אנא הכנס מיקום איסוף:"
    )
    
    return PICKUP

async def get_pickup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get pickup location from user"""
    user_id = str(update.effective_user.id)
    pickup = update.message.text.strip()
    
    user_data[user_id]['current_car']['pickup'] = pickup
    
    await update.message.reply_text(
        f"📍 איסוף מ: {pickup}\n\n"
        "אנא הכנס מיקום הורדה:"
    )
    
    return DROPOFF

async def get_dropoff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get drop-off location from user"""
    user_id = str(update.effective_user.id)
    dropoff = update.message.text.strip()
    
    user_data[user_id]['current_car']['dropoff'] = dropoff
    
    await update.message.reply_text(
        f"📍 הורדה ב: {dropoff}\n\n"
        "📝 אנא הכנס הערה:"
    )
    
    return NOTE

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle note input"""
    user_id = str(update.effective_user.id)
    note = update.message.text.strip()
    
    user_data[user_id]['current_car']['note'] = note
    
    # Create job type keyboard
    reply_keyboard = [[job_type] for job_type in JOB_TYPES]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📝 הערה: {note}\n\n"
        "איזה סוג משימה זה?",
        reply_markup=markup
    )
    
    return JOB_TYPE

async def handle_job_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle job type selection"""
    user_id = str(update.effective_user.id)
    job_type = update.message.text.strip()
    
    if job_type not in JOB_TYPES:
        await update.message.reply_text(
            "אנא בחר אחד מסוגי המשימות הזמינים:",
            reply_markup=ReplyKeyboardMarkup([[job_type] for job_type in JOB_TYPES], 
                                           one_time_keyboard=True, resize_keyboard=True)
        )
        return JOB_TYPE
    
    user_data[user_id]['current_car']['job_type'] = job_type
    
    # Add current car to daily list
    user_data[user_id]['daily_cars'].append(user_data[user_id]['current_car'].copy())
    
    # Update monthly stats
    current_month = datetime.now().strftime("%Y-%m")
    monthly_stats[f"{user_id}_{current_month}"] += 1
    
    save_data()
    
    reply_keyboard = [['רכב הבא', 'סיום יום']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    car_info = user_data[user_id]['current_car']
    await update.message.reply_text(
        f"✅ רכב נרשם בהצלחה!\n\n"
        f"🚗 {car_info['car_number']}\n"
        f"📍 מ: {car_info['pickup']}\n"
        f"📍 אל: {car_info['dropoff']}\n"
        f"🏷️ סוג משימה: {car_info['job_type']}\n"
        f"📝 הערה: {car_info['note'] if car_info['note'] else 'אין'}\n"
        f"⏰ זמן: {car_info['timestamp']}\n\n"
        "מה תרצה לעשות הלאה?",
        reply_markup=markup
    )
    
    return NEXT_OR_END

async def handle_next_or_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle next car or end day choice"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    if choice == "רכב הבא":
        user_data[user_id]['current_car'] = {}
        await update.message.reply_text(
            "🚗 רכב הבא מוכן!\n\n"
            "אנא הכנס מספר רכב:",
            reply_markup=ReplyKeyboardRemove()
        )
        return CAR_NUMBER
    
    elif choice == "סיום יום":
        return await end_day(update, context)
    
    return NEXT_OR_END

async def end_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End the day and show summary"""
    user_id = str(update.effective_user.id)
    daily_cars = user_data[user_id]['daily_cars']
    
    if not daily_cars:
        await update.message.reply_text(
            "📊 לא נרשמו רכבים היום!\n\n"
            "השתמש ב /start כדי להתחיל מעקב.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Calculate job statistics
    job_stats = defaultdict(int)
    for car in daily_cars:
        job_stats[car['job_type']] += 1
    
    # Generate summary for display
    summary = f"📊 **תנועת רכבים היום - {datetime.now().strftime('%Y-%m-%d')}**\n\n"
    summary += f"סך כולל המשימות: {len(daily_cars)}\n\n"
    
    # Job type statistics
    for job_type in JOB_TYPES:
        count = job_stats.get(job_type, 0)
        summary += f"{job_type}: {count}\n"
    
    summary += "\n" + "=" * 30 + "\n\n"
    
    for i, car in enumerate(daily_cars, 1):
        summary += f"**משימה #{i}**\n"
        summary += f"🚗 מספר רכב: {car['car_number']}\n"
        summary += f"📍 מאיפה: {car['pickup']}\n"
        summary += f"📍 לאיפה: {car['dropoff']}\n"
        summary += f"🏷️ סוג משימה: {car['job_type']}\n"
        if car['note']:
            summary += f"📝 הערות: {car['note']}\n"
        summary += f"⏰ זמן: {car['timestamp']}\n"
        summary += "─" * 30 + "\n\n"
    
    # Monthly stats
    current_month = datetime.now().strftime("%Y-%m")
    monthly_total = monthly_stats[f"{user_id}_{current_month}"]
    summary += f"📅 **סה\"כ החודש: {monthly_total} משימות**\n\n"
    summary += "צלם את הסיכום! 📸"
    
    # Generate plain text copy version
    copy_text = f"תנועת רכבים היום - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    copy_text += f"סך כולל המשימות: {len(daily_cars)}\n\n"
    
    for job_type in JOB_TYPES:
        count = job_stats.get(job_type, 0)
        copy_text += f"{job_type}: {count}\n"
    
    copy_text += "\n" + "=" * 30 + "\n\n"
    
    for i, car in enumerate(daily_cars, 1):
        copy_text += f"משימה #{i}\n"
        copy_text += f"מספר רכב: {car['car_number']}\n"
        copy_text += f"מאיפה: {car['pickup']}\n"
        copy_text += f"לאיפה: {car['dropoff']}\n"
        copy_text += f"סוג משימה: {car['job_type']}\n"
        if car['note']:
            copy_text += f"הערות: {car['note']}\n"
        copy_text += f"זמן: {car['timestamp']}\n"
        copy_text += "------------------------------\n\n"
    
    copy_text += f"סה\"כ החודש: {monthly_total} משימות"
    
    await update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    
    # Send copyable version
    await update.message.reply_text(
        f"📋 **גרסה להעתקה:**\n\n`{copy_text}`",
        parse_mode='Markdown'
    )
    
    # Send email summary
    try:
        send_daily_email(daily_cars, job_stats)
        await update.message.reply_text("📧 דו\"ח יומי נשלח במייל!")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        await update.message.reply_text("⚠️ שליחת המייל נכשלה - בדוק את הלוגים")
    
    # Clear daily data for next day
    user_data[user_id]['daily_cars'] = []
    save_data()
    
    await update.message.reply_text(
        "היום הסתיים! השתמש ב /start כדי להתחיל מעקב חדש.\n"
        "השתמש ב /stats כדי לראות את הסטטיסטיקות החודשיות.\n\n"
        "💡 טיפ: לחץ החזק על הגרסה להעתקה למעלה כדי להעתיק את הטקסט בקלות!"
    )
    
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show monthly statistics"""
    user_id = str(update.effective_user.id)
    current_month = datetime.now().strftime("%Y-%m")
    
    stats_text = f"📊 **סטטיסטיקות חודשיות**\n\n"
    stats_text += f"📅 החודש הנוכחי ({current_month}):\n"
    stats_text += f"🚗 סה\"כ משימות: {monthly_stats[f'{user_id}_{current_month}']}\n\n"
    
    # Show last 3 months
    for i in range(1, 4):
        past_date = datetime.now() - timedelta(days=30*i)
        past_month = past_date.strftime("%Y-%m")
        past_total = monthly_stats[f"{user_id}_{past_month}"]
        if past_total > 0:
            stats_text += f"📅 {past_month}: {past_total} משימות\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    await update.message.reply_text(
        "🚫 מעקב רכבים בוטל. השתמש ב /start כדי להתחיל שוב.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    """Start the bot"""
    # Load existing data
    load_data()
    
    # Get bot token from environment variable
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        logger.error("BOT_TOKEN environment variable not set!")
        return
    
    # Create the Application
    application = Application.builder().token(bot_token).build()
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_number)],
            PICKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pickup)],
            DROPOFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dropoff)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note)],
            JOB_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_job_type)],
            NEXT_OR_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_next_or_end)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('stats', stats))
    
    # Run the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
