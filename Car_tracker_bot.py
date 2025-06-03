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
import re

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation   states - MODIFIED: Added new states for editing and deletion
START, CAR_NUMBER, PICKUP, DROPOFF, NOTE, JOB_TYPE, NEXT_OR_END, EMAIL_MANAGEMENT, EMAIL_ADD, EMAIL_REMOVE, EDIT_DELETE_CHOICE, EDIT_ENTRY, DELETE_ENTRY = range(13)

# Data storage (in production, use a proper database)
user_data = {}
monthly_stats = defaultdict(int)
email_lists = {}  # Store email lists per user

# Default email configuration
DEFAULT_EMAIL_RECIPIENTS = [
    "email1@example.com",
    "email2@example.com", 
    "email3@example.com"
]

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# Hardcoded email credentials
EMAIL_USER = "Avivpeten123456789@gmail.com"
EMAIL_PASSWORD = "ycqx xqaf xicz ywgi"

# Job types in Hebrew
JOB_TYPES = [
    "משימת שינוע",
    "משימת טרמפ", 
    "משימת סרק",
    "משימת מוסך",
    "משימת טסט"
]

def format_car_number(car_number):
    """Format car number from 11111111 to 111-11-111"""
    # Remove any existing formatting
    cleaned = re.sub(r'[^0-9]', '', car_number)
    
    # Check if it's exactly 8 digits
    if len(cleaned) == 8:
        return f"{cleaned[:3]}-{cleaned[3:5]}-{cleaned[5:]}"
    else:
        # Return original if not 8 digits
        return car_number

def load_data():
    """Load user data from file"""
    global user_data, monthly_stats, email_lists
    try:
        if os.path.exists('user_data.json'):
            with open('user_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                user_data = data.get('user_data', {})
                monthly_stats = defaultdict(int, data.get('monthly_stats', {}))
                email_lists = data.get('email_lists', {})
        else:
            user_data = {}
            monthly_stats = defaultdict(int)
            email_lists = {}
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        user_data = {}
        monthly_stats = defaultdict(int)
        email_lists = {}

def save_data():
    """Save user data to file"""
    try:
        data = {
            'user_data': user_data,
            'monthly_stats': dict(monthly_stats),
            'email_lists': email_lists
        }
        with open('user_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def get_user_emails(user_id):
    """Get email list for specific user, return default if not set"""
    return email_lists.get(user_id, DEFAULT_EMAIL_RECIPIENTS.copy())

def send_daily_email(user_id, daily_cars, job_stats):
    """Send daily summary via email"""
    try:
        recipients = get_user_emails(user_id)
        if not recipients:
            logger.warning("No email recipients configured")
            return False
            
        # Create email content
        subject = f"דוח רכבים יומי - {datetime.now().strftime('%Y-%m-%d')}"
        
        body = f"דוח רכבים יומי - {datetime.now().strftime('%Y-%m-%d')}\n\n"
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
        
        for recipient in recipients:
            msg['To'] = recipient
            text = msg.as_string()
            server.sendmail(EMAIL_USER, recipient, text)
            del msg['To']
        
        server.quit()
        logger.info("Daily email sent successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the car tracking session"""
    user_id = str(update.effective_user.id)
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {
            'daily_cars': [],
            'current_car': {}
        }
    
    # Initialize email list if not exists
    if user_id not in email_lists:
        email_lists[user_id] = DEFAULT_EMAIL_RECIPIENTS.copy()
    
    # Clear current car data for new session
    user_data[user_id]['current_car'] = {}
    
    await update.message.reply_text(
        "🚗 מעקב רכבים החל!\n\n"
        "אנא הכנס מספר רכב (8 ספרות):"
    )
    
    return CAR_NUMBER

async def get_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get car number from user"""
    user_id = str(update.effective_user.id)
    car_number_input = update.message.text.strip()
    
    # Format the car number
    formatted_car_number = format_car_number(car_number_input)
    
    user_data[user_id]['current_car']['car_number'] = formatted_car_number
    user_data[user_id]['current_car']['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    await update.message.reply_text(
        f"🚗 מספר רכב: {formatted_car_number}\n\n"
        "אנא הכנס כתובת איסוף:"
    )
    
    return PICKUP

async def get_pickup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get pickup location from user"""
    user_id = str(update.effective_user.id)
    pickup = update.message.text.strip()
    
    user_data[user_id]['current_car']['pickup'] = pickup
    
    await update.message.reply_text(
        f"📍 איסוף: {pickup}\n\n"
        "אנא הכנס כתובת יעד:"
    )
    
    return DROPOFF

async def get_dropoff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get drop-off location from user"""
    user_id = str(update.effective_user.id)
    dropoff = update.message.text.strip()
    
    user_data[user_id]['current_car']['dropoff'] = dropoff
    
    await update.message.reply_text(
        f"📍 יעד: {dropoff}\n\n"
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
    
    # MODIFIED: Added editing and deletion options to the keyboard
    reply_keyboard = [['רכב הבא', 'סיום יום'], ['עריכה', 'מחיקה']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    car_info = user_data[user_id]['current_car']
    await update.message.reply_text(
        f"✅ הרכב נרשם!\n\n"
        f"🚗 {car_info['car_number']}\n"
        f"📍 מאיפה: {car_info['pickup']}\n"
        f"📍 לאיפה: {car_info['dropoff']}\n"
        f"🏷️ סוג משימה: {car_info['job_type']}\n"
        f"📝 הערה: {car_info['note'] if car_info['note'] else 'אין'}\n"
        f"⏰ זמן: {car_info['timestamp']}\n\n"
        "מה תרצה לעשות הלאה?",
        reply_markup=markup
    )
    
    return NEXT_OR_END

async def handle_next_or_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle next car, end day, edit, or delete choice - MODIFIED"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    if choice == "רכב הבא":
        user_data[user_id]['current_car'] = {}
        await update.message.reply_text(
            "🚗 רכב הבא מוכן!\n\n"
            "אנא הכנס מספר רכב (8 ספרות):",
            reply_markup=ReplyKeyboardRemove()
        )
        return CAR_NUMBER
    
    elif choice == "סיום יום":
        return await end_day(update, context)
    
    # NEW: Handle editing and deletion options
    elif choice == "עריכה":
        return await show_edit_options(update, context)
    
    elif choice == "מחיקה":
        return await show_delete_options(update, context)
    
    return NEXT_OR_END

# NEW FUNCTIONS: Edit and Delete functionality
async def show_edit_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of entries for editing"""
    user_id = str(update.effective_user.id)
    daily_cars = user_data[user_id]['daily_cars']
    
    if not daily_cars:
        await update.message.reply_text(
            "אין רכבים לעריכה!",
            reply_markup=ReplyKeyboardRemove()
        )
        return NEXT_OR_END
    
    # Create list of entries
    entries_text = "📝 **בחר רכב לעריכה:**\n\n"
    reply_keyboard = []
    
    for i, car in enumerate(daily_cars, 1):
        entries_text += f"{i}. {car['car_number']} - {car['pickup']} → {car['dropoff']}\n"
        reply_keyboard.append([f"{i}"])
    
    reply_keyboard.append(['ביטול'])
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        entries_text,
        reply_markup=markup,
        parse_mode='Markdown'
    )
    
    return EDIT_ENTRY

async def show_delete_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of entries for deletion"""
    user_id = str(update.effective_user.id)
    daily_cars = user_data[user_id]['daily_cars']
    
    if not daily_cars:
        await update.message.reply_text(
            "אין רכבים למחיקה!",
            reply_markup=ReplyKeyboardRemove()
        )
        return NEXT_OR_END
    
    # Create list of entries
    entries_text = "🗑️ **בחר רכב למחיקה:**\n\n"
    reply_keyboard = []
    
    for i, car in enumerate(daily_cars, 1):
        entries_text += f"{i}. {car['car_number']} - {car['pickup']} → {car['dropoff']}\n"
        reply_keyboard.append([f"{i}"])
    
    reply_keyboard.append(['ביטול'])
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        entries_text,
        reply_markup=markup,
        parse_mode='Markdown'
    )
    
    return DELETE_ENTRY

# NEW FUNCTIONS: Handle actual editing and deletion
async def handle_edit_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle editing a specific entry"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    if choice == "ביטול":
        reply_keyboard = [['רכב הבא', 'סיום יום'], ['עריכה', 'מחיקה']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "עריכה בוטלה. מה תרצה לעשות?",
            reply_markup=markup
        )
        return NEXT_OR_END
    
    try:
        entry_index = int(choice) - 1
        daily_cars = user_data[user_id]['daily_cars']
        
        if 0 <= entry_index < len(daily_cars):
            # Store the entry being edited
            context.user_data['editing_index'] = entry_index
            car = daily_cars[entry_index]
            
            # Show current details and editing options
            edit_options = [
                ['מספר רכב', 'נקודת איסוף'],
                ['נקודת יעד', 'הערה'],
                ['סוג משימה', 'סיים עריכה']
            ]
            markup = ReplyKeyboardMarkup(edit_options, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                f"🔧 **עריכת רכב:**\n\n"
                f"🚗 מספר רכב: {car['car_number']}\n"
                f"📍 מאיפה: {car['pickup']}\n"
                f"📍 לאיפה: {car['dropoff']}\n"
                f"🏷️ סוג משימה: {car['job_type']}\n"
                f"📝 הערה: {car['note'] if car['note'] else 'אין'}\n\n"
                "איזה שדה תרצה לערוך?",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            return EDIT_DELETE_CHOICE
        else:
            await update.message.reply_text("מספר לא תקין. אנא נסה שוב:")
            return EDIT_ENTRY
            
    except ValueError:
        await update.message.reply_text("אנא הכנס מספר תקין:")
        return EDIT_ENTRY

async def handle_delete_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deleting a specific entry"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    if choice == "ביטול":
        reply_keyboard = [['רכב הבא', 'סיום יום'], ['עריכה', 'מחיקה']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "מחיקה בוטלה. מה תרצה לעשות?",
            reply_markup=markup
        )
        return NEXT_OR_END
    
    try:
        entry_index = int(choice) - 1
        daily_cars = user_data[user_id]['daily_cars']
        
        if 0 <= entry_index < len(daily_cars):
            deleted_car = daily_cars.pop(entry_index)
            
            # Update monthly stats (decrease by 1)
            current_month = datetime.now().strftime("%Y-%m")
            monthly_stats[f"{user_id}_{current_month}"] -= 1
            
            save_data()
            
            reply_keyboard = [['רכב הבא', 'סיום יום'], ['עריכה', 'מחיקה']]
            markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                f"🗑️ **רכב נמחק בהצלחה!**\n\n"
                f"🚗 {deleted_car['car_number']}\n"
                f"📍 {deleted_car['pickup']} → {deleted_car['dropoff']}\n\n"
                "מה תרצה לעשות הלאה?",
                reply_markup=markup,
                parse_mode='Markdown'
            )
            return NEXT_OR_END
        else:
            await update.message.reply_text("מספר לא תקין. אנא נסה שוב:")
            return DELETE_ENTRY
            
    except ValueError:
        await update.message.reply_text("אנא הכנס מספר תקין:")
        return DELETE_ENTRY

async def handle_edit_field_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle which field to edit"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    if choice == "סיים עריכה":
        reply_keyboard = [['רכב הבא', 'סיום יום'], ['עריכה', 'מחיקה']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "עריכה הושלמה! מה תרצה לעשות הלאה?",
            reply_markup=markup
        )
        return NEXT_OR_END
    
    editing_index = context.user_data.get('editing_index')
    if editing_index is None:
        return NEXT_OR_END
    
    context.user_data['editing_field'] = choice
    
    if choice == "מספר רכב":
        await update.message.reply_text(
            "🚗 הכנס מספר רכב חדש (8 ספרות):",
            reply_markup=ReplyKeyboardRemove()
        )
    elif choice == "נקודת איסוף":
        await update.message.reply_text(
            "📍 הכנס נקודת איסוף חדשה:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif choice == "נקודת יעד":
        await update.message.reply_text(
            "📍 הכנס נקודת יעד חדשה:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif choice == "הערה":
        await update.message.reply_text(
            "📝 הכנס הערה חדשה:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif choice == "סוג משימה":
        reply_keyboard = [[job_type] for job_type in JOB_TYPES]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🏷️ בחר סוג משימה חדש:",
            reply_markup=markup
        )
    
    return EDIT_DELETE_CHOICE

async def handle_field_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle updating the field value"""
    user_id = str(update.effective_user.id)
    new_value = update.message.text.strip()
    
    editing_index = context.user_data.get('editing_index')
    editing_field = context.user_data.get('editing_field')
    
    if editing_index is None or editing_field is None:
        return NEXT_OR_END
    
    daily_cars = user_data[user_id]['daily_cars']
    car = daily_cars[editing_index]
    
    # Update the appropriate field
    if editing_field == "מספר רכב":
        car['car_number'] = format_car_number(new_value)
    elif editing_field == "נקודת איסוף":
        car['pickup'] = new_value
    elif editing_field == "נקודת יעד":
        car['dropoff'] = new_value
    elif editing_field == "הערה":
        car['note'] = new_value
    elif editing_field == "סוג משימה":
        if new_value in JOB_TYPES:
            car['job_type'] = new_value
        else:
            await update.message.reply_text("סוג משימה לא תקין. אנא בחר מהרשימה:")
            return EDIT_DELETE_CHOICE
    
    save_data()
    
    # Show updated entry and continue editing options
    edit_options = [
        ['מספר רכב', 'נקודת איסוף'],
        ['נקודת יעד', 'הערה'],
        ['סוג משימה', 'סיים עריכה']
    ]
    markup = ReplyKeyboardMarkup(edit_options, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"✅ **שדה עודכן בהצלחה!**\n\n"
        f"🚗 מספר רכב: {car['car_number']}\n"
        f"📍 מאיפה: {car['pickup']}\n"
        f"📍 לאיפה: {car['dropoff']}\n"
        f"🏷️ סוג משימה: {car['job_type']}\n"
        f"📝 הערה: {car['note'] if car['note'] else 'אין'}\n\n"
        "איזה שדה נוסף תרצה לערוך?",
        reply_markup=markup,
        parse_mode='Markdown'
    )
    
    return EDIT_DELETE_CHOICE

async def end_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End the day and show summary, then ask about email management"""
    user_id = str(update.effective_user.id)
    daily_cars = user_data[user_id]['daily_cars']
    
    if not daily_cars:
        await update.message.reply_text(
            "📊 לא נרשמו רכבים היום!\n\n"
            "השתמש ב-/start כדי להתחיל מעקב.",
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
    summary += f"📅 **סה״כ החודש: {monthly_total} משימות**\n\n"
    summary += "צלם מסך של הסיכום! 📸"
    
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
    
    copy_text += f"סה״כ החודש: {monthly_total} משימות"
    
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
    
    # Store data for email management
    context.user_data['daily_cars'] = daily_cars
    context.user_data['job_stats'] = job_stats
    
    # Ask about email management
    current_emails = get_user_emails(user_id)
    email_list_text = "\n".join([f"• {email}" for email in current_emails])
    
    reply_keyboard = [['שלח דוח'], ['עריכת רשימת מיילים'], ['דלג']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📧 **רשימת מיילים נוכחית:**\n{email_list_text}\n\n"
        "האם תרצה לשלוח את הדוח היומי למיילים האלה?",
        reply_markup=markup
    )
    
    return EMAIL_MANAGEMENT

async def handle_email_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle email management choice"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    if choice == "שלח דוח":
        # Send email and finish
        daily_cars = context.user_data['daily_cars']
        job_stats = context.user_data['job_stats']
        
        success = send_daily_email(user_id, daily_cars, job_stats)
        if success:
            await update.message.reply_text("📧 דוח יומי נשלח באימייל!", reply_markup=ReplyKeyboardRemove())
        else:
            await update.message.reply_text("⚠️ שליחת האימייל נכשלה - בדוק לוגים", reply_markup=ReplyKeyboardRemove())
        
        return await finish_day(update, context)
        
    elif choice == "עריכת רשימת מיילים":
        current_emails = get_user_emails(user_id)
        email_list_text = "\n".join([f"{i+1}. {email}" for i, email in enumerate(current_emails)])
        
        reply_keyboard = [['הוסף מייל'], ['הסר מייל'], ['סיים עריכה']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"📧 **רשימת מיילים נוכחית:**\n{email_list_text}\n\n"
            "מה תרצה לעשות?",
            reply_markup=markup
        )
        
        return EMAIL_MANAGEMENT
        
    elif choice == "דלג":
        return await finish_day(update, context)
        
    elif choice == "הוסף מייל":
        await update.message.reply_text(
            "📧 אנא הכנס כתובת מייל חדשה:",
            reply_markup=ReplyKeyboardRemove()
        )
        return EMAIL_ADD
        
    elif choice == "הסר מייל":
        current_emails = get_user_emails(user_id)
        if not current_emails:
            await update.message.reply_text("אין מיילים להסרה!")
            return EMAIL_MANAGEMENT
            
        email_list_text = "\n".join([f"{i+1}. {email}" for i, email in enumerate(current_emails)])
        await update.message.reply_text(
            f"📧 **רשימת מיילים:**\n{email_list_text}\n\n"
            "אנא הכנס את המספר של המייל שברצונך להסיר:",
            reply_markup=ReplyKeyboardRemove()
        )
        return EMAIL_REMOVE
        
    elif choice == "סיים עריכה":
        # Ask again about sending email
        current_emails = get_user_emails(user_id)
        email_list_text = "\n".join([f"• {email}" for email in current_emails])
        
        reply_keyboard = [['שלח דוח'], ['דלג']]
        markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            f"📧 **רשימת מיילים מעודכנת:**\n{email_list_text}\n\n"
            "האם תרצה לשלוח את הדוח היומי למיילים האלה?",
            reply_markup=markup
        )
        
        return EMAIL_MANAGEMENT
    
    return EMAIL_MANAGEMENT

async def handle_email_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle adding new email"""
    user_id = str(update.effective_user.id)
    new_email = update.message.text.strip()
    
    # Basic email validation
    if '@' not in new_email or '.' not in new_email:
        await update.message.reply_text("❌ כתובת מייל לא תקינה. אנא נסה שוב:")
        return EMAIL_ADD
    
    # Add email to user's list
    if user_id not in email_lists:
        email_lists[user_id] = []
    
    if new_email not in email_lists[user_id]:
        email_lists[user_id].append(new_email)
        save_data()
        await update.message.reply_text(f"✅ המייל {new_email} נוסף בהצלחה!")
    else:
        await update.message.reply_text("המייל כבר קיים ברשימה!")
    
    # Return to email management
    current_emails = get_user_emails(user_id)
    email_list_text = "\n".join([f"{i+1}. {email}" for i, email in enumerate(current_emails)])
    
    reply_keyboard = [['הוסף מייל'], ['הסר מייל'], ['סיים עריכה']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📧 **רשימת מיילים מעודכנת:**\n{email_list_text}\n\n"
        "מה תרצה לעשות?",
        reply_markup=markup
    )
    
    return EMAIL_MANAGEMENT

async def handle_email_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle removing email"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    current_emails = get_user_emails(user_id)
    
    try:
        index = int(choice) - 1
        if 0 <= index < len(current_emails):
            removed_email = current_emails.pop(index)
            email_lists[user_id] = current_emails
            save_data()
            await update.message.reply_text(f"✅ המייל {removed_email} הוסר בהצלחה!")
        else:
            await update.message.reply_text("❌ מספר לא תקין. אנא נסה שוב:")
            return EMAIL_REMOVE
    except ValueError:
        await update.message.reply_text("❌ אנא הכנס מספר תקין:")
        return EMAIL_REMOVE
    
    # Return to email management
    current_emails = get_user_emails(user_id)
    email_list_text = "\n".join([f"{i+1}. {email}" for i, email in enumerate(current_emails)])
    
    reply_keyboard = [['הוסף מייל'], ['הסר מייל'], ['סיים עריכה']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📧 **רשימת מיילים מעודכנת:**\n{email_list_text}\n\n"
        "מה תרצה לעשות?",
        reply_markup=markup
    )
    
    return EMAIL_MANAGEMENT

async def finish_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Finish the day and clean up"""
    user_id = str(update.effective_user.id)
    
    # Clear daily data for next day
    user_data[user_id]['daily_cars'] = []
    save_data()
    
    await update.message.reply_text(
        "היום הסתיים! השתמש ב-/start כדי להתחיל מעקב חדש.\n"
        "השתמש ב-/stats כדי לראות את הסטטיסטיקות החודשיות.\n\n"
        "💡 טיפ: לחץ והחזק על הגרסה להעתקה למעלה כדי להעתיק בקלות את הטקסט!",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show monthly statistics"""
    user_id = str(update.effective_user.id)
    current_month = datetime.now().strftime("%Y-%m")
    
    stats_text = f"📊 **סטטיסטיקות חודשיות**\n\n"
    stats_text += f"📅 החודש הנוכחי ({current_month}):\n"
    stats_text += f"🚗 סה״כ משימות: {monthly_stats[f'{user_id}_{current_month}']}\n\n"
    
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
        "🚫 מעקב הרכבים בוטל. השתמש ב-/start כדי להתחיל שוב.",
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
    
    # Add conversation handler - MODIFIED: Added new states for editing and deletion
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_number)],
            PICKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pickup)],
            DROPOFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dropoff)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note)],
            JOB_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_job_type)],
            NEXT_OR_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_next_or_end)],
            EMAIL_MANAGEMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_management)],
            EMAIL_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_add)],
            EMAIL_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_remove)],
            # NEW STATES: Added handlers for editing and deletion
            EDIT_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_entry)],
            DELETE_ENTRY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_entry)],
            EDIT_DELETE_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_field_choice)],
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
