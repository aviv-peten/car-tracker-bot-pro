import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict
import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "8195716721:AAGfrro7LCy1WTr4QccCZgtnIJvt3M6CdVI"

# Email configuration  
EMAIL_USER = "Avivpeten123456789@gmail.com"
EMAIL_PASSWORD = "ycqx xqaf xicz ywgi"

# Job types in Hebrew
JOB_TYPES = {
    "שינוע": "משימת שינוע",
    "טרמפ": "משימת טרמפ", 
    "סרק": "משימת סרק",
    "מוסך": "משימת מוסך",
    "טסט": "משימת טסט"
}

# Data storage
user_data = {}
daily_jobs = {}
monthly_stats = defaultdict(lambda: defaultdict(int))
email_lists = {}

# Israel timezone
IST = pytz.timezone('Asia/Jerusalem')

def format_car_number(car_num):
    """Format 8-digit car number to XXX-XX-XXX format"""
    if len(car_num) == 8 and car_num.isdigit():
        return f"{car_num[:3]}-{car_num[3:5]}-{car_num[5:]}"
    return car_num

def get_current_time():
    """Get current time in Israel timezone"""
    return datetime.now(IST).strftime("%H:%M")

def get_today_key():
    """Get today's date as key"""
    return datetime.now(IST).strftime("%Y-%m-%d")

def get_month_key():
    """Get current month as key"""
    return datetime.now(IST).strftime("%Y-%m")

def get_main_menu_keyboard():
    """Get main menu keyboard"""
    return [
        ["רכב חדש", "סיום יום"],
        ["עריכה/מחיקה", "סטטיסטיקה חודשית"]
    ]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    
    # Initialize user data
    if user_id not in user_data:
        user_data[user_id] = {}
    if user_id not in daily_jobs:
        daily_jobs[user_id] = {}
    if user_id not in email_lists:
        email_lists[user_id] = []
    
    # Reset user state
    user_data[user_id]['state'] = 'main_menu'
    
    # Main menu keyboard
    keyboard = get_main_menu_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "ברוכים הבאים לבוט מעקב רכבים!\nאנא בחרו פעולה:",
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    user_id = update.effective_user.id
    text = update.message.text
    
    # Initialize user data if needed
    if user_id not in user_data:
        user_data[user_id] = {}
    if user_id not in daily_jobs:
        daily_jobs[user_id] = {}
        
    user_state = user_data[user_id].get('state', 'main_menu')
    
    # Handle main menu options
    if text == "רכב חדש":
        await new_car(update, context)
    elif text == "סיום יום":
        await end_day(update, context)
    elif text == "עריכה/מחיקה":
        await edit_delete(update, context)
    elif text == "סטטיסטיקה חודשית":
        await monthly_stats_handler(update, context)
    
    # Handle job type selection
    elif text in JOB_TYPES.values() and user_state == 'waiting_job_type':
        await handle_job_type(update, context)
    
    # Handle email choice
    elif text in ["שלח במייל", "דלג"] and user_state == 'waiting_email_choice':
        await handle_email_choice(update, context)
    
    # Handle state-specific inputs
    elif user_state == "waiting_car_number":
        await handle_car_number(update, context)
    elif user_state == "waiting_pickup":
        await handle_pickup(update, context)
    elif user_state == "waiting_delivery":
        await handle_delivery(update, context)
    elif user_state == "waiting_notes":
        await handle_notes(update, context)
    elif user_state == "waiting_email":
        await handle_email_input(update, context)
    else:
        # Return to main menu for any unrecognized input
        await return_to_main_menu(update, context)

async def return_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Return to main menu"""
    user_id = update.effective_user.id
    user_data[user_id]['state'] = 'main_menu'
    
    keyboard = get_main_menu_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("אנא בחרו פעולה:", reply_markup=reply_markup)

async def new_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new car entry process"""
    user_id = update.effective_user.id
    user_data[user_id]['state'] = 'waiting_car_number'
    user_data[user_id]['current_car'] = {}
    
    await update.message.reply_text(
        "אנא הזינו מספר רכב (8 ספרות):",
        reply_markup=ReplyKeyboardRemove()
    )

async def handle_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle car number input"""
    user_id = update.effective_user.id
    car_num = update.message.text.strip()
    
    if len(car_num) != 8 or not car_num.isdigit():
        await update.message.reply_text("אנא הזינו מספר רכב של 8 ספרות בדיוק:")
        return
    
    formatted_num = format_car_number(car_num)
    user_data[user_id]['current_car']['number'] = formatted_num
    user_data[user_id]['current_car']['time'] = get_current_time()
    user_data[user_id]['state'] = 'waiting_pickup'
    
    await update.message.reply_text(f"מספר רכב: {formatted_num}\nמאיפה נאסף הרכב?")

async def handle_pickup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pickup location input"""
    user_id = update.effective_user.id
    pickup = update.message.text.strip()
    
    user_data[user_id]['current_car']['pickup'] = pickup
    user_data[user_id]['state'] = 'waiting_delivery'
    
    await update.message.reply_text("איפה נמסר הרכב?")

async def handle_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle delivery location input"""
    user_id = update.effective_user.id
    delivery = update.message.text.strip()
    
    user_data[user_id]['current_car']['delivery'] = delivery
    user_data[user_id]['state'] = 'waiting_notes'
    
    await update.message.reply_text("הערות (אופציונלי):")

async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle notes input and show job type selection"""
    user_id = update.effective_user.id
    notes = update.message.text.strip()
    
    user_data[user_id]['current_car']['notes'] = notes
    user_data[user_id]['state'] = 'waiting_job_type'
    
    # Job type keyboard
    keyboard = [
        ["משימת שינוע", "משימת טרמפ"],
        ["משימת סרק", "משימת מוסך"],
        ["משימת טסט"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "איזה משימה עשיתה?",
        reply_markup=reply_markup
    )

async def handle_job_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle job type selection"""
    user_id = update.effective_user.id
    job_type = update.message.text.strip()
    
    if job_type not in JOB_TYPES.values():
        await update.message.reply_text("אנא בחרו סוג משימה מהרשימה:")
        return
    
    # Save the job
    today = get_today_key()
    if today not in daily_jobs[user_id]:
        daily_jobs[user_id][today] = []
    
    car_data = user_data[user_id]['current_car'].copy()
    car_data['job_type'] = job_type
    daily_jobs[user_id][today].append(car_data)
    
    # Update monthly stats
    month = get_month_key()
    job_key = list(JOB_TYPES.keys())[list(JOB_TYPES.values()).index(job_type)]
    monthly_stats[user_id][month] += 1
    monthly_stats[user_id][f"{month}_{job_key}"] += 1
    
    # Reset state and return to main menu
    user_data[user_id]['state'] = 'main_menu'
    user_data[user_id]['current_car'] = {}
    
    # Main menu keyboard
    keyboard = get_main_menu_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    job_count = len(daily_jobs[user_id][today])
    await update.message.reply_text(
        f"המשימה נשמרה בהצלחה!\nסך הכל משימות היום: {job_count}",
        reply_markup=reply_markup
    )

async def edit_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's jobs for editing/deleting"""
    user_id = update.effective_user.id
    today = get_today_key()
    
    # Reset state
    user_data[user_id]['state'] = 'main_menu'
    
    if today not in daily_jobs[user_id] or not daily_jobs[user_id][today]:
        keyboard = get_main_menu_keyboard()
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("אין משימות היום למחיקה או עריכה.", reply_markup=reply_markup)
        return
    
    # Create inline keyboard for each job
    keyboard = []
    for i, job in enumerate(daily_jobs[user_id][today]):
        job_text = f"משימה {i+1}: {job['number']} - {job['job_type']}"
        keyboard.append([InlineKeyboardButton(f"🗑 מחק {job_text}", callback_data=f"delete_{i}")])
    
    keyboard.append([InlineKeyboardButton("חזור לתפריט הראשי", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("בחרו משימה למחיקה:", reply_markup=reply_markup)

async def monthly_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show monthly statistics"""
    user_id = update.effective_user.id
    current_date = datetime.now(IST)
    
    # Reset state
    user_data[user_id]['state'] = 'main_menu'
    
    stats_text = "📊 סטטיסטיקה חודשית:\n\n"
    
    # Show stats for current month and 3 months back
    for i in range(4):
        month_date = current_date - timedelta(days=30*i)
        month_key = month_date.strftime("%Y-%m")
        month_name = month_date.strftime("%m/%Y")
        
        total_jobs = monthly_stats[user_id].get(month_key, 0)
        stats_text += f"📅 {month_name}: {total_jobs} משימות\n"
        
        for job_key, job_name in JOB_TYPES.items():
            count = monthly_stats[user_id].get(f"{month_key}_{job_key}", 0)
            if count > 0:
                stats_text += f"  • {job_name}: {count}\n"
        stats_text += "\n"
    
    keyboard = get_main_menu_keyboard()
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(stats_text, reply_markup=reply_markup)

async def end_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End day summary"""
    user_id = update.effective_user.id
    today = get_today_key()
    
    if today not in daily_jobs[user_id] or not daily_jobs[user_id][today]:
        keyboard = get_main_menu_keyboard()
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("אין משימות היום.", reply_markup=reply_markup)
        return
    
    jobs = daily_jobs[user_id][today]
    total_jobs = len(jobs)
    
    # Count job types
    job_counts = defaultdict(int)
    for job in jobs:
        job_key = list(JOB_TYPES.keys())[list(JOB_TYPES.values()).index(job['job_type'])]
        job_counts[job_key] += 1
    
    # Create summary
    summary = f"📊 סיכום יום {datetime.now(IST).strftime('%d/%m/%Y')}:\n\n"
    summary += f"סך כולל המשימות: {total_jobs}\n"
    
    for job_key, job_name in JOB_TYPES.items():
        count = job_counts[job_key]
        summary += f"{job_name}: {count}\n"
    
    summary += "\n" + "="*30 + "\n"
    
    # Add detailed job list
    for i, job in enumerate(jobs, 1):
        summary += f"\nמשימה {i}:\n"
        summary += f"מספר רכב: {job['number']}\n"
        summary += f"נאסף: {job['pickup']}\n"
        summary += f"נמסר: {job['delivery']}\n"
        summary += f"הערות: {job['notes']}\n"
        summary += f"סוג משימה: {job['job_type']}\n"
        summary += f"שעה: {job['time']}\n"
        summary += "-" * 20 + "\n"
    
    # Store summary for email
    user_data[user_id]['daily_summary'] = summary
    user_data[user_id]['state'] = 'waiting_email_choice'
    
    # Email options
    keyboard = [
        ["שלח במייל", "דלג"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(summary + "\nלשלוח במייל?", reply_markup=reply_markup)

async def handle_email_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email sending choice"""
    user_id = update.effective_user.id
    choice = update.message.text.strip()
    
    if choice == "שלח במייל":
        await show_email_list(update, context)
    elif choice == "דלג":
        # Clear today's jobs and return to main menu
        today = get_today_key()
        if today in daily_jobs[user_id]:
            del daily_jobs[user_id][today]
        
        user_data[user_id]['state'] = 'main_menu'
        keyboard = get_main_menu_keyboard()
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("יום חדש התחיל! בהצלחה!", reply_markup=reply_markup)

async def show_email_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show email list management"""
    user_id = update.effective_user.id
    
    if not email_lists[user_id]:
        user_data[user_id]['state'] = 'waiting_email'
        await update.message.reply_text("אין כתובות מייל ברשימה.\nהזינו כתובת מייל:")
        return
    
    # Show current emails with options
    keyboard = []
    for i, email in enumerate(email_lists[user_id]):
        keyboard.append([InlineKeyboardButton(f"🗑 מחק {email}", callback_data=f"delete_email_{i}")])
    
    keyboard.append([InlineKeyboardButton("➕ הוסף מייל חדש", callback_data="add_email")])
    keyboard.append([InlineKeyboardButton("📧 שלח לכולם", callback_data="send_emails")])
    keyboard.append([InlineKeyboardButton("חזור לתפריט", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    emails_text = "📧 רשימת מיילים:\n" + "\n".join(email_lists[user_id])
    await update.message.reply_text(emails_text, reply_markup=reply_markup)

async def handle_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new email input"""
    user_id = update.effective_user.id
    email = update.message.text.strip()
    
    if "@" not in email:
        await update.message.reply_text("אנא הזינו כתובת מייל תקינה:")
        return
    
    email_lists[user_id].append(email)
    user_data[user_id]['state'] = 'main_menu'
    
    await update.message.reply_text(f"המייל {email} נוסף בהצלחה!")
    await show_email_list(update, context)

async def send_emails(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Send daily summary via email"""
    if user_id not in email_lists or not email_lists[user_id]:
        return False
    
    try:
        summary = user_data[user_id].get('daily_summary', '')
        if not summary:
            return False
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['Subject'] = f"סיכום יום - {datetime.now(IST).strftime('%d/%m/%Y')}"
        
        body = summary
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Send to all emails
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        
        for email in email_lists[user_id]:
            msg['To'] = email
            server.send_message(msg)
            del msg['To']
        
        server.quit()
        return True
        
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        return False

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button callbacks"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    
    if data.startswith("delete_"):
        # Delete job
        job_index = int(data.split("_")[1])
        today = get_today_key()
        
        if today in daily_jobs[user_id] and job_index < len(daily_jobs[user_id][today]):
            deleted_job = daily_jobs[user_id][today].pop(job_index)
            
            # Update monthly stats
            month = get_month_key()
            job_key = list(JOB_TYPES.keys())[list(JOB_TYPES.values()).index(deleted_job['job_type'])]
            monthly_stats[user_id][month] -= 1
            monthly_stats[user_id][f"{month}_{job_key}"] -= 1
            
            await query.edit_message_text("המשימה נמחקה בהצלחה!")
            
        # Return to main menu
        user_data[user_id]['state'] = 'main_menu'
        keyboard = get_main_menu_keyboard()
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await context.bot.send_message(user_id, "חזרה לתפריט הראשי:", reply_markup=reply_markup)
        
    elif data.startswith("delete_email_"):
        # Delete email
        email_index = int(data.split("_")[2])
        if email_index < len(email_lists[user_id]):
            email_lists[user_id].pop(email_index)
        await show_email_list_callback(query, context)
        
    elif data == "add_email":
        user_data[user_id]['state'] = 'waiting_email'
        await query.edit_message_text("הזינו כתובת מייל חדשה:")
        
    elif data == "send_emails":
        success = await send_emails(user_id, context)
        if success:
            # Clear today's jobs
            today = get_today_key()
            if today in daily_jobs[user_id]:
                del daily_jobs[user_id][today]
            
            await query.edit_message_text("המיילים נשלחו בהצלחה! יום חדש התחיל!")
        else:
            await query.edit_message_text("שגיאה בשליחת המיילים.")
        
        # Return to main menu
        user_data[user_id]['state'] = 'main_menu'
        keyboard = get_main_menu_keyboard()
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await context.bot.send_message(user_id, "חזרה לתפריט הראשי:", reply_markup=reply_markup)
        
    elif data == "main_menu":
        user_data[user_id]['state'] = 'main_menu'
        keyboard = get_main_menu_keyboard()
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await query.edit_message_text("תפריט ראשי:")
        await context.bot.send_message(user_id, "אנא בחרו פעולה:", reply_markup=reply_markup)

async def show_email_list_callback(query, context):
    """Show email list in callback context"""
    user_id = query.from_user.id
    
    if not email_lists[user_id]:
        await query.edit_message_text("אין מיילים ברשימה.")
        return
    
    keyboard = []
    for i, email in enumerate(email_lists[user_id]):
        keyboard.append([InlineKeyboardButton(f"🗑 מחק {email}", callback_data=f"delete_email_{i}")])
    
    keyboard.append([InlineKeyboardButton("➕ הוסף מייל חדש", callback_data="add_email")])
    keyboard.append([InlineKeyboardButton("📧 שלח לכולם", callback_data="send_emails")])
    keyboard.append([InlineKeyboardButton("חזור לתפריט", callback_data="main_menu")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    emails_text = "📧 רשימת מיילים:\n" + "\n".join(email_lists[user_id])
    await query.edit_message_text(emails_text, reply_markup=reply_markup)

def main():
    """Main function to run the bot"""
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
