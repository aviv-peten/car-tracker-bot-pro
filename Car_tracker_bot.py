import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import json
import os

# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8195716721:AAGfrro7LCy1WTr4QccCZgtnIJvt3M6CdVI"
EMAIL_ADDRESS = "Avivpeten123456789@gmail.com"
EMAIL_PASSWORD = "ycqx xqaf xicz ywgi"

# In-memory data storage
cars_data = {}  # {date: [car_entries]}
monthly_stats = {}  # {month: {job_type: count}}
email_list = []  # List of email addresses
user_states = {}  # Track user conversation states

# Job types in Hebrew
JOB_TYPES = {
    "משימת שינוע": "shipping",
    "משימת טרמפ": "hitchhike", 
    "משימת סרק": "empty",
    "משימת טסט": "test",
    "משימת מוסך": "garage"
}

def format_car_number(car_num):
    """Format car number from 11111111 to 111-11-111"""
    if len(car_num) == 8 and car_num.isdigit():
        return f"{car_num[:3]}-{car_num[3:5]}-{car_num[5:]}"
    return car_num

def get_main_keyboard():
    """Create main menu keyboard"""
    keyboard = [
        [KeyboardButton("רכב הבא")],
        [KeyboardButton("סיום יום")],
        [KeyboardButton("עריכה/מחיקה")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_job_types_keyboard():
    """Create job types keyboard"""
    keyboard = []
    for job_type in JOB_TYPES.keys():
        keyboard.append([KeyboardButton(job_type)])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    user_states[user_id] = {"state": "main_menu"}
    
    await update.message.reply_text(
        "ברוך הבא! בחר אפשרות:",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_states:
        user_states[user_id] = {"state": "main_menu"}
    
    state = user_states[user_id]["state"]
    
    # Main menu options
    if text == "רכב הבא":
        user_states[user_id] = {"state": "waiting_car_number"}
        await update.message.reply_text("הכנס מספר רכב (8 ספרות):")
        
    elif text == "סיום יום":
        await handle_end_of_day(update, context)
        
    elif text == "עריכה/מחיקה":
        await handle_edit_delete(update, context)
        
    # Car entry flow
    elif state == "waiting_car_number":
        if len(text) == 8 and text.isdigit():
            formatted_car = format_car_number(text)
            user_states[user_id]["car_number"] = formatted_car
            user_states[user_id]["state"] = "waiting_pickup"
            await update.message.reply_text(f"מספר רכב: {formatted_car}\nמאיפה לקחת את הרכב?")
        else:
            await update.message.reply_text("אנא הכנס מספר רכב תקין (8 ספרות):")
            
    elif state == "waiting_pickup":
        user_states[user_id]["pickup"] = text
        user_states[user_id]["state"] = "waiting_dropoff"
        await update.message.reply_text("לאן להחזיר את הרכב?")
        
    elif state == "waiting_dropoff":
        user_states[user_id]["dropoff"] = text
        user_states[user_id]["state"] = "waiting_notes"
        await update.message.reply_text("הערות (אופציונלי - לחץ /skip כדי לדלג):")
        
    elif state == "waiting_notes":
        if text != "/skip":
            user_states[user_id]["notes"] = text
        else:
            user_states[user_id]["notes"] = ""
        user_states[user_id]["state"] = "waiting_job_type"
        await update.message.reply_text(
            "בחר סוג משימה:",
            reply_markup=get_job_types_keyboard()
        )
        
    elif state == "waiting_job_type" and text in JOB_TYPES:
        # Save the car entry
        today = date.today().isoformat()
        if today not in cars_data:
            cars_data[today] = []
            
        car_entry = {
            "car_number": user_states[user_id]["car_number"],
            "pickup": user_states[user_id]["pickup"],
            "dropoff": user_states[user_id]["dropoff"],
            "notes": user_states[user_id].get("notes", ""),
            "job_type": text,
            "time": datetime.now().strftime("%H:%M")
        }
        
        cars_data[today].append(car_entry)
        
        # Update monthly stats
        current_month = datetime.now().strftime("%Y-%m")
        if current_month not in monthly_stats:
            monthly_stats[current_month] = {job: 0 for job in JOB_TYPES.keys()}
        monthly_stats[current_month][text] += 1
        
        user_states[user_id] = {"state": "main_menu"}
        
        await update.message.reply_text(
            f"נשמר בהצלחה!\n"
            f"רכב: {car_entry['car_number']}\n"
            f"מ: {car_entry['pickup']}\n"
            f"אל: {car_entry['dropoff']}\n"
            f"משימה: {car_entry['job_type']}\n"
            f"שעה: {car_entry['time']}",
            reply_markup=get_main_keyboard()
        )
        
    else:
        await update.message.reply_text("בחר אפשרות מהתפריט:", reply_markup=get_main_keyboard())

async def handle_end_of_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle end of day summary"""
    today = date.today().isoformat()
    current_month = datetime.now().strftime("%Y-%m")
    
    # Today's summary
    today_cars = cars_data.get(today, [])
    today_summary = {"סך הכול": len(today_cars)}
    
    for job_type in JOB_TYPES.keys():
        count = sum(1 for car in today_cars if car["job_type"] == job_type)
        today_summary[job_type] = count
    
    # Monthly summary
    monthly_summary = monthly_stats.get(current_month, {job: 0 for job in JOB_TYPES.keys()})
    total_monthly = sum(monthly_summary.values())
    
    summary_text = f"דוח יומי - {datetime.now().strftime('%d/%m/%Y')}\n\n"
    summary_text += "היום:\n"
    for job_type, count in today_summary.items():
        summary_text += f"{job_type}: {count}\n"
    
    summary_text += f"\nהחודש עד כה:\n"
    summary_text += f"סך הכול: {total_monthly}\n"
    for job_type, count in monthly_summary.items():
        summary_text += f"{job_type}: {count}\n"
    
    # Detailed car list for today
    if today_cars:
        summary_text += f"\nרשימת רכבים היום:\n"
        for i, car in enumerate(today_cars, 1):
            summary_text += f"{i}. {car['car_number']} ({car['time']})\n"
            summary_text += f"   {car['pickup']} → {car['dropoff']}\n"
            summary_text += f"   {car['job_type']}\n"
            if car['notes']:
                summary_text += f"   הערות: {car['notes']}\n"
            summary_text += "\n"
    
    await update.message.reply_text(summary_text)
    
    # Ask about email
    keyboard = [[InlineKeyboardButton("כן", callback_data="send_email_yes"),
                 InlineKeyboardButton("לא", callback_data="send_email_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "האם לשלוח דוח במייל?",
        reply_markup=reply_markup
    )

async def handle_edit_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle edit/delete cars for today"""
    today = date.today().isoformat()
    today_cars = cars_data.get(today, [])
    
    if not today_cars:
        await update.message.reply_text("אין רכבים להיום", reply_markup=get_main_keyboard())
        return
    
    keyboard = []
    for i, car in enumerate(today_cars):
        keyboard.append([InlineKeyboardButton(
            f"{car['car_number']} - {car['job_type']} ({car['time']})",
            callback_data=f"edit_car_{i}"
        )])
    
    keyboard.append([InlineKeyboardButton("חזור לתפריט", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("בחר רכב לעריכה/מחיקה:", reply_markup=reply_markup)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "send_email_yes":
        await send_email_dialog(update, context)
    elif query.data == "send_email_no":
        await query.edit_message_text("חזור לתפריט הראשי")
        await query.message.reply_text("בחר אפשרות:", reply_markup=get_main_keyboard())
    elif query.data == "back_to_menu":
        await query.edit_message_text("חזור לתפריט הראשי")
        await query.message.reply_text("בחר אפשרות:", reply_markup=get_main_keyboard())
    elif query.data.startswith("edit_car_"):
        car_index = int(query.data.split("_")[2])
        await handle_car_edit_options(update, context, car_index)

async def handle_car_edit_options(update: Update, context: ContextTypes.DEFAULT_TYPE, car_index: int):
    """Show edit/delete options for a specific car"""
    keyboard = [
        [InlineKeyboardButton("מחק", callback_data=f"delete_car_{car_index}")],
        [InlineKeyboardButton("חזור", callback_data="back_to_edit_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    today = date.today().isoformat()
    car = cars_data[today][car_index]
    
    car_info = f"רכב: {car['car_number']}\n"
    car_info += f"מ: {car['pickup']}\n"
    car_info += f"אל: {car['dropoff']}\n"
    car_info += f"משימה: {car['job_type']}\n"
    car_info += f"שעה: {car['time']}"
    
    await update.callback_query.edit_message_text(car_info, reply_markup=reply_markup)

async def send_email_dialog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email sending dialog"""
    # For now, just send to the default email
    today = date.today().isoformat()
    today_cars = cars_data.get(today, [])
    
    if not today_cars:
        await update.callback_query.edit_message_text("אין נתונים לשליחה")
        return
    
    # Create email content
    subject = f"דוח יומי - {datetime.now().strftime('%d/%m/%Y')}"
    
    body = f"דוח יומי - {datetime.now().strftime('%d/%m/%Y')}\n\n"
    
    # Today's summary
    today_summary = {}
    for job_type in JOB_TYPES.keys():
        count = sum(1 for car in today_cars if car["job_type"] == job_type)
        today_summary[job_type] = count
    
    body += "סיכום היום:\n"
    body += f"סך הכול: {len(today_cars)}\n"
    for job_type, count in today_summary.items():
        body += f"{job_type}: {count}\n"
    
    body += f"\nרשימת רכבים:\n"
    for i, car in enumerate(today_cars, 1):
        body += f"{i}. {car['car_number']} ({car['time']})\n"
        body += f"   {car['pickup']} → {car['dropoff']}\n"
        body += f"   {car['job_type']}\n"
        if car['notes']:
            body += f"   הערות: {car['notes']}\n"
        body += "\n"
    
    # Send email
    try:
        send_email(subject, body, [EMAIL_ADDRESS])
        await update.callback_query.edit_message_text("הדוח נשלח בהצלחה!")
    except Exception as e:
        await update.callback_query.edit_message_text(f"שגיאה בשליחת המייל: {str(e)}")
    
    # Return to main menu
    await update.callback_query.message.reply_text("בחר אפשרות:", reply_markup=get_main_keyboard())

def send_email(subject: str, body: str, recipients: list):
    """Send email using Gmail SMTP"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Start the bot
    application.run_polling()

if __name__ == '__main__':
    main()
