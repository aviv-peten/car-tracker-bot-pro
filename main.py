import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import os
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

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
    'transport': 'משימת שינוע',
    'empty': 'משימת סרק', 
    'hitchhike': 'משימת טרמפ',
    'garage': 'משימת מוסך',
    'test': 'משימת טסט'
}

# Data storage (in production, use a proper database)
user_data = {}
monthly_stats = {}
email_lists = {}

def get_user_data(user_id):
    if user_id not in user_data:
        user_data[user_id] = {
            'current_job': {},
            'daily_jobs': [],
            'state': 'main_menu',
            'edit_job_index': -1
        }
    return user_data[user_id]

def get_monthly_stats(user_id):
    if user_id not in monthly_stats:
        monthly_stats[user_id] = {}
    return monthly_stats[user_id]

def get_email_list(user_id):
    if user_id not in email_lists:
        email_lists[user_id] = []
    return email_lists[user_id]

def format_car_number(number_str):
    """Format 8-digit car number to XXX-XX-XXX"""
    # Remove all non-digits
    digits_only = re.sub(r'\D', '', number_str)
    if len(digits_only) == 8:
        return f"{digits_only[:3]}-{digits_only[3:5]}-{digits_only[5:]}"
    return number_str

def create_main_menu():
    """Create main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("רכב חדש", callback_data="new_car")],
        [InlineKeyboardButton("סיום יום", callback_data="end_day")],
        [InlineKeyboardButton("עריכה/מחיקה", callback_data="edit_delete")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_job_type_keyboard():
    """Create job type selection keyboard"""
    keyboard = []
    for key, value in JOB_TYPES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"job_{key}")])
    return InlineKeyboardMarkup(keyboard)

def create_yes_no_keyboard():
    """Create yes/no keyboard"""
    keyboard = [
        [InlineKeyboardButton("כן", callback_data="yes")],
        [InlineKeyboardButton("דלג", callback_data="no")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    get_user_data(user_id)['state'] = 'main_menu'
    
    await update.message.reply_text(
        "ברוך הבא למערכת מעקב רכבים!\nבחר פעולה:",
        reply_markup=create_main_menu()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    callback_data = query.data
    
    # Main menu handlers
    if callback_data == "new_car":
        data['state'] = 'car_number'
        data['current_job'] = {}
        await query.edit_message_text("הכנס מספר רכב (8 ספרות):")
    
    elif callback_data == "end_day":
        await handle_end_day(query, user_id)
    
    elif callback_data == "edit_delete":
        await handle_edit_delete(query, user_id)
    
    # Job type handlers
    elif callback_data.startswith("job_"):
        job_type = callback_data.replace("job_", "")
        data['current_job']['job_type'] = job_type
        
        # Save the job
        data['daily_jobs'].append(data['current_job'].copy())
        job_name = JOB_TYPES[job_type]
        car_num = data['current_job']['car_number']
        
        await query.edit_message_text(
            f"המשימה נשמרה בהצלחה!\n"
            f"רכב: {car_num}\n"
            f"סוג משימה: {job_name}\n\n"
            f"בחר פעולה נוספת:",
            reply_markup=create_main_menu()
        )
        data['state'] = 'main_menu'
    
    # Email handlers
    elif callback_data in ["yes", "no"]:
        if callback_data == "yes":
            await handle_email_selection(query, user_id)
        else:
            await query.edit_message_text(
                "סיום יום הושלם!\nבחר פעולה:",
                reply_markup=create_main_menu()
            )
            data['state'] = 'main_menu'
    
    # Edit/Delete handlers
    elif callback_data.startswith("edit_"):
        job_index = int(callback_data.replace("edit_", ""))
        data['edit_job_index'] = job_index
        await handle_job_edit(query, user_id, job_index)
    
    elif callback_data.startswith("delete_"):
        job_index = int(callback_data.replace("delete_", ""))
        data['daily_jobs'].pop(job_index)
        await query.edit_message_text("המשימה נמחקה!")
        await handle_edit_delete(query, user_id)

async def handle_end_day(query, user_id):
    """Handle end of day statistics"""
    data = get_user_data(user_id)
    jobs = data['daily_jobs']
    
    if not jobs:
        await query.edit_message_text(
            "אין משימות להיום\nבחר פעולה:",
            reply_markup=create_main_menu()
        )
        return
    
    # Calculate daily stats
    total_jobs = len(jobs)
    job_counts = Counter([job['job_type'] for job in jobs])
    
    # Update monthly stats
    today = datetime.now().strftime("%Y-%m")
    stats = get_monthly_stats(user_id)
    if today not in stats:
        stats[today] = {'total_days': 0, 'total_jobs': 0, 'job_types': Counter()}
    
    stats[today]['total_days'] += 1
    stats[today]['total_jobs'] += total_jobs
    stats[today]['job_types'].update(job_counts)
    
    # Create summary
    summary = f"סיכום יום:\n"
    summary += f"סה\"כ משימות: {total_jobs}\n\n"
    
    for job_type, count in job_counts.items():
        job_name = JOB_TYPES[job_type]
        summary += f"{job_name}: {count}\n"
    
    summary += f"\nסטטיסטיקות חודשיות:\n"
    summary += f"ימי עבודה החודש: {stats[today]['total_days']}\n"
    summary += f"סה\"כ משימות החודש: {stats[today]['total_jobs']}\n"
    
    summary += "\nלשלוח דו\"ח במייל?"
    
    await query.edit_message_text(summary, reply_markup=create_yes_no_keyboard())

async def handle_email_selection(query, user_id):
    """Handle email selection and sending"""
    data = get_user_data(user_id)
    jobs = data['daily_jobs']
    
    # Create email content
    today = datetime.now().strftime("%d/%m/%Y")
    email_content = f"דו\"ח יומי - {today}\n\n"
    
    total_jobs = len(jobs)
    job_counts = Counter([job['job_type'] for job in jobs])
    
    email_content += f"סה\"כ משימות: {total_jobs}\n\n"
    
    for job_type, count in job_counts.items():
        job_name = JOB_TYPES[job_type]
        email_content += f"{job_name}: {count}\n"
    
    email_content += "\n\nפירוט משימות:\n"
    for i, job in enumerate(jobs, 1):
        job_name = JOB_TYPES[job['job_type']]
        email_content += f"{i}. רכב {job['car_number']} - {job_name}\n"
        email_content += f"   מ: {job.get('pickup', 'לא צוין')}\n"
        email_content += f"   ל: {job.get('dropoff', 'לא צוין')}\n"
        if job.get('notes'):
            email_content += f"   הערות: {job['notes']}\n"
        email_content += "\n"
    
    try:
        # Send email
        await send_email("דו\"ח יומי", email_content, [EMAIL_USER])
        
        # Clear daily data after successful email send
        data['daily_jobs'] = []
        
        await query.edit_message_text(
            "הדו\"ח נשלח בהצלחה!\nהמידע היומי נמחק.\n\nבחר פעולה:",
            reply_markup=create_main_menu()
        )
    except Exception as e:
        await query.edit_message_text(
            f"שגיאה בשליחת המייל: {str(e)}\n\nבחר פעולה:",
            reply_markup=create_main_menu()
        )
    
    data['state'] = 'main_menu'

async def send_email(subject, body, recipients):
    """Send email using SMTP"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(EMAIL_USER, EMAIL_PASSWORD)
    text = msg.as_string()
    server.sendmail(EMAIL_USER, recipients, text)
    server.quit()

async def handle_edit_delete(query, user_id):
    """Handle edit/delete menu"""
    data = get_user_data(user_id)
    jobs = data['daily_jobs']
    
    if not jobs:
        await query.edit_message_text(
            "אין משימות לעריכה היום\nבחר פעולה:",
            reply_markup=create_main_menu()
        )
        return
    
    keyboard = []
    for i, job in enumerate(jobs):
        job_name = JOB_TYPES[job['job_type']]
        car_num = job['car_number']
        keyboard.append([
            InlineKeyboardButton(f"ערוך: {car_num} - {job_name}", callback_data=f"edit_{i}"),
            InlineKeyboardButton("מחק", callback_data=f"delete_{i}")
        ])
    
    keyboard.append([InlineKeyboardButton("חזור לתפריט הראשי", callback_data="main_menu")])
    
    await query.edit_message_text(
        "בחר משימה לעריכה או מחיקה:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_job_edit(query, user_id, job_index):
    """Handle individual job editing"""
    data = get_user_data(user_id)
    job = data['daily_jobs'][job_index]
    
    job_name = JOB_TYPES[job['job_type']]
    job_details = f"עריכת משימה:\n"
    job_details += f"רכב: {job['car_number']}\n"
    job_details += f"סוג: {job_name}\n"
    job_details += f"איסוף: {job.get('pickup', 'לא צוין')}\n"
    job_details += f"הורדה: {job.get('dropoff', 'לא צוין')}\n"
    job_details += f"הערות: {job.get('notes', 'אין')}\n\n"
    job_details += "איזה פרט תרצה לערוך?"
    
    keyboard = [
        [InlineKeyboardButton("מיקום איסוף", callback_data="edit_pickup")],
        [InlineKeyboardButton("מיקום הורדה", callback_data="edit_dropoff")],
        [InlineKeyboardButton("הערות", callback_data="edit_notes")],
        [InlineKeyboardButton("סוג משימה", callback_data="edit_job_type")],
        [InlineKeyboardButton("חזור", callback_data="edit_delete")]
    ]
    
    await query.edit_message_text(job_details, reply_markup=InlineKeyboardMarkup(keyboard))

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    text = update.message.text
    
    if data['state'] == 'car_number':
        # Validate car number (8 digits)
        digits_only = re.sub(r'\D', '', text)
        if len(digits_only) != 8:
            await update.message.reply_text(f"מספר רכב חייב להיות 8 ספרות. קיבלתי: {len(digits_only)} ספרות\nהכנס מספר רכב תקין:")
            return
        
        formatted_number = format_car_number(digits_only)
        data['current_job']['car_number'] = formatted_number
        data['state'] = 'pickup_location'
        await update.message.reply_text("הכנס מיקום איסוף:")
    
    elif data['state'] == 'pickup_location':
        data['current_job']['pickup'] = text
        data['state'] = 'dropoff_location'
        await update.message.reply_text("הכנס מיקום הורדה:")
    
    elif data['state'] == 'dropoff_location':
        data['current_job']['dropoff'] = text
        data['state'] = 'notes'
        await update.message.reply_text("הכנס הערות (או שלח כל טקסט לדילוג):")
    
    elif data['state'] == 'notes':
        data['current_job']['notes'] = text
        data['state'] = 'job_type'
        await update.message.reply_text(
            "בחר סוג משימה:",
            reply_markup=create_job_type_keyboard()
        )

def main():
    """Main function"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    # Start the bot
    port = int(os.environ.get('PORT', 8000))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=BOT_TOKEN,
        webhook_url=f"https://your-railway-app.up.railway.app/{BOT_TOKEN}"
    )

if __name__ == '__main__':
    main()
