import telebot
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from collections import defaultdict
import calendar
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Bot                  Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "8195716721:AAGfrro7LCy1WTr4QccCZgtnIJvt3M6CdVI")
bot = telebot.TeleBot(BOT_TOKEN)

# Email configuration
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "Avivpeten123456789@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "ycqx xqaf xicz ywgi")

# Data files - use /tmp for Railway
DATA_DIR = "/tmp" if os.path.exists("/tmp") else "."
DATA_FILE = os.path.join(DATA_DIR, "car_tracker_data.json")
EMAILS_FILE = os.path.join(DATA_DIR, "email_list.json")

# Job types in Hebrew
JOB_TYPES = [
    "משימת שינוע",
    "משימת סרק", 
    "משימת טרמפ",
    "משימת מוסך",
    "משימת טסט"
]

# User states
user_states = {}
temp_data = {}

def load_data():
    """Load data from JSON file"""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading data: {e}")
    return {}

def save_data(data):
    """Save data to JSON file"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

def load_emails():
    """Load email list from JSON file"""
    try:
        if os.path.exists(EMAILS_FILE):
            with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading emails: {e}")
    return []

def save_emails(emails):
    """Save email list to JSON file"""
    try:
        with open(EMAILS_FILE, 'w', encoding='utf-8') as f:
            json.dump(emails, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving emails: {e}")

def get_today_key():
    """Get today's date key"""
    return datetime.now().strftime("%Y-%m-%d")

def get_month_key(date_obj):
    """Get month key from date object"""
    return date_obj.strftime("%Y-%m")

def format_car_number(number):
    """Format car number to XXX-XX-XXX"""
    if len(number) == 8:
        return f"{number[:3]}-{number[3:5]}-{number[5:]}"
    return number

def get_hebrew_month_name(month_num):
    """Get Hebrew month name"""
    months = {
        1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
        5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
        9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר"
    }
    return months.get(month_num, str(month_num))

def create_main_menu():
    """Create main menu keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("רכב חדש", "סוף יום")
    markup.add("עריכה/מחיקה", "סטטיסטיקות")
    return markup

def create_number_keyboard():
    """Create number keyboard for car input"""
    markup = telebot.types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    for i in range(1, 10):
        buttons.append(telebot.types.InlineKeyboardButton(str(i), callback_data=f"num_{i}"))
    buttons.append(telebot.types.InlineKeyboardButton("0", callback_data="num_0"))
    buttons.append(telebot.types.InlineKeyboardButton("מחק", callback_data="num_delete"))
    buttons.append(telebot.types.InlineKeyboardButton("אישור", callback_data="num_confirm"))
    
    markup.add(*buttons[:3])
    markup.add(*buttons[3:6])
    markup.add(*buttons[6:9])
    markup.add(buttons[9], buttons[10], buttons[11])
    return markup

def create_job_type_keyboard():
    """Create job type selection keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for job_type in JOB_TYPES:
        markup.add(job_type)
    return markup

def create_yes_no_keyboard():
    """Create yes/no keyboard"""
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("כן", "דלג")
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    """Handle start command"""
    user_states[message.chat.id] = "main_menu"
    bot.send_message(
        message.chat.id,
        "ברוך הבא למעקב רכבים!\nבחר פעולה:",
        reply_markup=create_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "רכב חדש")
def new_car(message):
    """Handle new car entry"""
    user_states[message.chat.id] = "entering_car_number"
    temp_data[message.chat.id] = {"car_number": ""}
    
    bot.send_message(
        message.chat.id,
        "הכנס מספר רכב (8 ספרות):\n\nמספר נוכחי: ",
        reply_markup=create_number_keyboard()
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("num_"))
def handle_number_input(call):
    """Handle number keyboard input"""
    try:
        if call.message.chat.id not in temp_data:
            return
        
        if call.data == "num_delete":
            if temp_data[call.message.chat.id]["car_number"]:
                temp_data[call.message.chat.id]["car_number"] = temp_data[call.message.chat.id]["car_number"][:-1]
        elif call.data == "num_confirm":
            car_number = temp_data[call.message.chat.id]["car_number"]
            if len(car_number) == 8:
                formatted_number = format_car_number(car_number)
                temp_data[call.message.chat.id]["formatted_car_number"] = formatted_number
                user_states[call.message.chat.id] = "entering_pickup"
                
                bot.edit_message_text(
                    f"מספר רכב: {formatted_number}\n\nהכנס מקום איסוף:",
                    call.message.chat.id,
                    call.message.message_id
                )
                return
            else:
                bot.answer_callback_query(call.id, "חובה להכניס 8 ספרות")
                return
        else:  # Regular number
            number = call.data.split("_")[1]
            if len(temp_data[call.message.chat.id]["car_number"]) < 8:
                temp_data[call.message.chat.id]["car_number"] += number
        
        current_number = temp_data[call.message.chat.id]["car_number"]
        bot.edit_message_text(
            f"הכנס מספר רכב (8 ספרות):\n\nמספר נוכחי: {current_number}",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=create_number_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in handle_number_input: {e}")
        bot.answer_callback_query(call.id, "שגיאה, נסה שוב")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "entering_pickup")
def handle_pickup(message):
    """Handle pickup location input"""
    temp_data[message.chat.id]["pickup"] = message.text
    user_states[message.chat.id] = "entering_dropoff"
    bot.send_message(message.chat.id, "הכנס מקום הורדה:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "entering_dropoff")
def handle_dropoff(message):
    """Handle dropoff location input"""
    temp_data[message.chat.id]["dropoff"] = message.text
    user_states[message.chat.id] = "entering_note"
    bot.send_message(message.chat.id, "הכנס הערה:")

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "entering_note")
def handle_note(message):
    """Handle note input"""
    temp_data[message.chat.id]["note"] = message.text
    user_states[message.chat.id] = "selecting_job_type"
    bot.send_message(
        message.chat.id,
        "בחר סוג משימה:",
        reply_markup=create_job_type_keyboard()
    )

@bot.message_handler(func=lambda message: message.text in JOB_TYPES and user_states.get(message.chat.id) == "selecting_job_type")
def handle_job_type(message):
    """Handle job type selection"""
    # Save the job
    data = load_data()
    today = get_today_key()
    
    if today not in data:
        data[today] = []
    
    job = {
        "car_number": temp_data[message.chat.id]["formatted_car_number"],
        "pickup": temp_data[message.chat.id]["pickup"],
        "dropoff": temp_data[message.chat.id]["dropoff"],
        "note": temp_data[message.chat.id]["note"],
        "job_type": message.text,
        "time": datetime.now().strftime("%H:%M")
    }
    
    data[today].append(job)
    save_data(data)
    
    # Clear temp data
    del temp_data[message.chat.id]
    user_states[message.chat.id] = "main_menu"
    
    bot.send_message(
        message.chat.id,
        f"המשימה נשמרה בהצלחה!\n\nרכב: {job['car_number']}\nמ: {job['pickup']}\nל: {job['dropoff']}\nהערה: {job['note']}\nסוג: {job['job_type']}",
        reply_markup=create_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "סוף יום")
def end_of_day(message):
    """Handle end of day summary"""
    data = load_data()
    today = get_today_key()
    
    if today not in data or not data[today]:
        bot.send_message(
            message.chat.id,
            "אין משימות להיום",
            reply_markup=create_main_menu()
        )
        return
    
    jobs = data[today]
    
    # Count job types
    job_counts = defaultdict(int)
    for job in jobs:
        job_counts[job['job_type']] += 1
    
    # Create summary message
    summary = f"סיכום היום ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    summary += f"סך הכל: {len(jobs)} משימות\n\n"
    
    for job_type, count in job_counts.items():
        summary += f"{job_type}: {count}\n"
    
    summary += "\nפירוט המשימות:\n\n"
    
    for i, job in enumerate(jobs, 1):
        summary += f"משימה {i}:\n"
        summary += f"רכב: {job['car_number']}\n"
        summary += f"מ: {job['pickup']}\n"
        summary += f"ל: {job['dropoff']}\n"
        summary += f"הערה: {job['note']}\n"
        summary += f"סוג: {job['job_type']}\n"
        summary += f"שעה: {job['time']}\n\n"
    
    bot.send_message(message.chat.id, summary)
    
    # Update monthly statistics
    current_date = datetime.now()
    month_key = get_month_key(current_date)
    
    if 'monthly_stats' not in data:
        data['monthly_stats'] = {}
    
    if month_key not in data['monthly_stats']:
        data['monthly_stats'][month_key] = 0
    
    data['monthly_stats'][month_key] += len(jobs)
    save_data(data)
    
    # Ask about email
    user_states[message.chat.id] = "asking_email"
    temp_data[message.chat.id] = {"daily_summary": summary, "job_counts": dict(job_counts), "total_jobs": len(jobs)}
    
    bot.send_message(
        message.chat.id,
        "האם לשלוח דוח במייל?",
        reply_markup=create_yes_no_keyboard()
    )

@bot.message_handler(func=lambda message: message.text in ["כן", "דלג"] and user_states.get(message.chat.id) == "asking_email")
def handle_email_choice(message):
    """Handle email choice"""
    if message.text == "כן":
        emails = load_emails()
        if not emails:
            bot.send_message(
                message.chat.id,
                "אין כתובות מייל שמורות.\nהכנס כתובת מייל:"
            )
            user_states[message.chat.id] = "adding_email"
            return
        
        # Show email list
        user_states[message.chat.id] = "selecting_emails"
        temp_data[message.chat.id]["selected_emails"] = []
        show_email_list(message.chat.id)
    else:
        # Skip email and finish
        finish_end_of_day(message.chat.id)

def show_email_list(chat_id):
    """Show email list for selection"""
    emails = load_emails()
    markup = telebot.types.InlineKeyboardMarkup()
    
    for i, email in enumerate(emails):
        selected = "✓ " if email in temp_data[chat_id]["selected_emails"] else ""
        markup.add(telebot.types.InlineKeyboardButton(
            f"{selected}{email}",
            callback_data=f"email_toggle_{i}"
        ))
    
    markup.add(telebot.types.InlineKeyboardButton("הוסף מייל חדש", callback_data="add_email"))
    markup.add(telebot.types.InlineKeyboardButton("מחק מייל", callback_data="delete_email"))
    markup.add(telebot.types.InlineKeyboardButton("שלח לנבחרים", callback_data="send_emails"))
    markup.add(telebot.types.InlineKeyboardButton("דלג", callback_data="skip_emails"))
    
    bot.send_message(
        chat_id,
        "בחר כתובות מייל לשליחה:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("email_"))
def handle_email_callback(call):
    """Handle email-related callbacks"""
    emails = load_emails()
    
    if call.data.startswith("email_toggle_"):
        email_index = int(call.data.split("_")[2])
        email = emails[email_index]
        
        if email in temp_data[call.message.chat.id]["selected_emails"]:
            temp_data[call.message.chat.id]["selected_emails"].remove(email)
        else:
            temp_data[call.message.chat.id]["selected_emails"].append(email)
        
        # Update the message
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
        show_email_list(call.message.chat.id)
        
    elif call.data == "send_emails":
        selected_emails = temp_data[call.message.chat.id]["selected_emails"]
        if selected_emails:
            send_daily_email(call.message.chat.id, selected_emails)
        else:
            bot.answer_callback_query(call.id, "לא נבחרו כתובות מייל")
            
    elif call.data == "skip_emails":
        bot.edit_message_text(
            "דילוג על שליחת מייל",
            call.message.chat.id,
            call.message.message_id
        )
        finish_end_of_day(call.message.chat.id)

def send_daily_email(chat_id, email_addresses):
    """Send daily summary email"""
    try:
        summary_data = temp_data[chat_id]
        
        # Create email content
        subject = f"דוח יומי - {datetime.now().strftime('%d/%m/%Y')}"
        
        body = f"סך הכל היום: {summary_data['total_jobs']} משימות\n\n"
        
        for job_type, count in summary_data['job_counts'].items():
            body += f"{job_type}: {count}\n"
        
        body += "\n" + summary_data['daily_summary']
        
        # Send email
        msg = MIMEMultipart()
        msg['From'] = "Automatically car tracker massage"
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        
        for email in email_addresses:
            msg['To'] = email
            server.send_message(msg)
            del msg['To']
        
        server.quit()
        
        bot.send_message(chat_id, f"דוח נשלח בהצלחה ל-{len(email_addresses)} כתובות")
        finish_end_of_day(chat_id)
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        bot.send_message(chat_id, f"שגיאה בשליחת מייל: {str(e)}")
        finish_end_of_day(chat_id)

def finish_end_of_day(chat_id):
    """Finish end of day process"""
    # Clear today's jobs
    data = load_data()
    today = get_today_key()
    if today in data:
        del data[today]
        save_data(data)
    
    # Clear temp data
    if chat_id in temp_data:
        del temp_data[chat_id]
    
    user_states[chat_id] = "main_menu"
    
    bot.send_message(
        chat_id,
        "סוף יום הושלם!\nנתוני היום נמחקו ומחכים למחר.",
        reply_markup=create_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "סטטיסטיקות")
def show_statistics(message):
    """Show monthly statistics"""
    data = load_data()
    
    if 'monthly_stats' not in data:
        bot.send_message(
            message.chat.id,
            "אין נתונים סטטיסטיים",
            reply_markup=create_main_menu()
        )
        return
    
    current_date = datetime.now()
    stats_message = "סטטיסטיקות חודשיות:\n\n"
    
    # Show current month and 3 months back
    for i in range(4):
        month_date = current_date - timedelta(days=30*i)
        month_key = get_month_key(month_date)
        month_name = get_hebrew_month_name(month_date.month)
        year = month_date.year
        
        count = data['monthly_stats'].get(month_key, 0)
        
        if i == 0:
            stats_message += f"חודש נוכחי ({month_name} {year}): {count} משימות\n"
        else:
            stats_message += f"לפני {i} חודש{'ים' if i > 1 else ''} ({month_name} {year}): {count} משימות\n"
    
    bot.send_message(
        message.chat.id,
        stats_message,
        reply_markup=create_main_menu()
    )

@bot.message_handler(func=lambda message: message.text == "עריכה/מחיקה")
def edit_delete(message):
    """Handle edit/delete functionality"""
    data = load_data()
    today = get_today_key()
    
    if today not in data or not data[today]:
        bot.send_message(
            message.chat.id,
            "אין משימות להיום לעריכה",
            reply_markup=create_main_menu()
        )
        return
    
    jobs = data[today]
    markup = telebot.types.InlineKeyboardMarkup()
    
    for i, job in enumerate(jobs):
        markup.add(telebot.types.InlineKeyboardButton(
            f"משימה {i+1}: {job['car_number']} - {job['job_type']}",
            callback_data=f"edit_{i}"
        ))
    
    markup.add(telebot.types.InlineKeyboardButton("חזרה לתפריט", callback_data="back_to_menu"))
    
    bot.send_message(
        message.chat.id,
        "בחר משימה לעריכה או מחיקה:",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_"))
def handle_edit_callback(call):
    """Handle edit callback"""
    job_index = int(call.data.split("_")[1])
    data = load_data()
    today = get_today_key()
    
    if today not in data or job_index >= len(data[today]):
        bot.answer_callback_query(call.id, "משימה לא נמצאה")
        return
    
    job = data[today][job_index]
    
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("מחק משימה", callback_data=f"delete_{job_index}"))
    markup.add(telebot.types.InlineKeyboardButton("חזרה", callback_data="back_to_edit"))
    
    job_details = f"משימה {job_index + 1}:\n"
    job_details += f"רכב: {job['car_number']}\n"
    job_details += f"מ: {job['pickup']}\n"
    job_details += f"ל: {job['dropoff']}\n"
    job_details += f"הערה: {job['note']}\n"
    job_details += f"סוג: {job['job_type']}\n"
    job_details += f"שעה: {job['time']}"
    
    bot.edit_message_text(
        job_details,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_"))
def handle_delete_callback(call):
    """Handle delete callback"""
    job_index = int(call.data.split("_")[1])
    data = load_data()
    today = get_today_key()
    
    if today not in data or job_index >= len(data[today]):
        bot.answer_callback_query(call.id, "משימה לא נמצאה")
        return
    
    # Delete the job
    del data[today][job_index]
    save_data(data)
    
    bot.edit_message_text(
        "המשימה נמחקה בהצלחה",
        call.message.chat.id,
        call.message.message_id
    )
    
    # Go back to main menu
    bot.send_message(
        call.message.chat.id,
        "חזרה לתפריט הראשי",
        reply_markup=create_main_menu()
    )

@bot.callback_query_handler(func=lambda call: call.data == "back_to_menu")
def back_to_menu(call):
    """Go back to main menu"""
    user_states[call.message.chat.id] = "main_menu"
    bot.edit_message_text(
        "תפריט ראשי",
        call.message.chat.id,
        call.message.message_id
    )
    bot.send_message(
        call.message.chat.id,
        "בחר פעולה:",
        reply_markup=create_main_menu()
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == "adding_email")
def handle_add_email(message):
    """Handle adding new email"""
    email = message.text.strip()
    if "@" in email and "." in email:
        emails = load_emails()
        if email not in emails:
            emails.append(email)
            save_emails(emails)
            bot.send_message(message.chat.id, f"מייל {email} נוסף בהצלחה")
        else:
            bot.send_message(message.chat.id, "המייל כבר קיים")
        
        # Go back to email selection
        user_states[message.chat.id] = "selecting_emails"
        temp_data[message.chat.id]["selected_emails"] = [email]
        show_email_list(message.chat.id)
    else:
        bot.send_message(message.chat.id, "כתובת מייל לא תקינה, נסה שוב:")

# Default message handler
@bot.message_handler(func=lambda message: True)
def default_handler(message):
    """Handle all other messages"""
    bot.send_message(
        message.chat.id,
        "לא הבנתי. בחר אפשרות מהתפריט:",
        reply_markup=create_main_menu()
    )

if __name__ == "__main__":
    try:
        logger.info("Bot starting...")
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        # Try to restart
        import time
        time.sleep(5)
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
