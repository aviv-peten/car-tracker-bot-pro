import logging
import sqlite3
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import re
import json
import os

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "8195716721:AAGfrro7LCy1WTr4QcCZgtnIJvt3M6CdVI"

# Email configuration
EMAIL_USER = "Avivpeten123456789@gmail.com"
EMAIL_PASSWORD = "ycqx xqaf xicz ywgi"

# Job types in Hebrew
JOB_TYPES = {
    'שינוע': 'משימת שינוע',
    'טרמפ': 'משימת טרמפ', 
    'סרק': 'משימת סרק',
    'מוסך': 'משימת מוסך',
    'טסט': 'משימת טסט'
}

# Database setup
def init_db():
    conn = sqlite3.connect('car_jobs.db')
    c = conn.cursor()
    
    # Cars table
    c.execute('''CREATE TABLE IF NOT EXISTS cars
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  car_number TEXT,
                  pickup_location TEXT,
                  delivery_location TEXT,
                  notes TEXT,
                  job_type TEXT,
                  date TEXT,
                  time TEXT,
                  user_id INTEGER)''')
    
    # Email list table
    c.execute('''CREATE TABLE IF NOT EXISTS emails
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  email TEXT UNIQUE,
                  user_id INTEGER)''')
    
    conn.commit()
    conn.close()

# User states for conversation handling
USER_STATES = {}
TEMP_CAR_DATA = {}

class UserState:
    MAIN_MENU = 0
    WAITING_CAR_NUMBER = 1
    WAITING_PICKUP = 2
    WAITING_DELIVERY = 3
    WAITING_NOTES = 4
    WAITING_JOB_TYPE = 5
    EDIT_DELETE_MENU = 6
    WAITING_EMAIL = 7
    EMAIL_MANAGEMENT = 8

def get_main_keyboard():
    keyboard = [
        ['רכב חדש', 'סיום יום'],
        ['עריכה/מחיקה', 'סטטיסטיקה חודשית']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_job_type_keyboard():
    keyboard = [
        ['משימת שינוע', 'משימת טרמפ'],
        ['משימת סרק', 'משימת מוסך'],
        ['משימת טסט']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_email_keyboard():
    keyboard = [
        ['כן', 'דלג']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def format_car_number(car_number):
    """Format 8-digit car number to XXX-XX-XXX"""
    if len(car_number) == 8 and car_number.isdigit():
        return f"{car_number[:3]}-{car_number[3:5]}-{car_number[5:]}"
    return car_number

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_STATES[user_id] = UserState.MAIN_MENU
    
    await update.message.reply_text(
        'ברוך הבא לבוט ניהול רכבים! 🚗\nבחר פעולה:',
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in USER_STATES:
        USER_STATES[user_id] = UserState.MAIN_MENU
    
    state = USER_STATES[user_id]
    
    if text == 'רכב חדש':
        await new_car(update, context)
    elif text == 'סיום יום':
        await end_of_day(update, context)
    elif text == 'עריכה/מחיקה':
        await edit_delete_menu(update, context)
    elif text == 'סטטיסטיקה חודשית':
        await monthly_stats(update, context)
    elif state == UserState.WAITING_CAR_NUMBER:
        await handle_car_number(update, context)
    elif state == UserState.WAITING_PICKUP:
        await handle_pickup(update, context)
    elif state == UserState.WAITING_DELIVERY:
        await handle_delivery(update, context)
    elif state == UserState.WAITING_NOTES:
        await handle_notes(update, context)
    elif state == UserState.WAITING_JOB_TYPE:
        await handle_job_type(update, context)
    elif state == UserState.WAITING_EMAIL:
        await handle_email_choice(update, context)
    else:
        await update.message.reply_text(
            'אנא בחר פעולה מהתפריט הראשי:',
            reply_markup=get_main_keyboard()
        )

async def new_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_STATES[user_id] = UserState.WAITING_CAR_NUMBER
    TEMP_CAR_DATA[user_id] = {}
    
    await update.message.reply_text('אנא הכנס מספר רכב (8 ספרות):')

async def handle_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    car_number = update.message.text.strip()
    
    if len(car_number) == 8 and car_number.isdigit():
        formatted_number = format_car_number(car_number)
        TEMP_CAR_DATA[user_id]['car_number'] = formatted_number
        USER_STATES[user_id] = UserState.WAITING_PICKUP
        
        await update.message.reply_text(f'מספר רכב: {formatted_number}\nמאיפה נאסף הרכב?')
    else:
        await update.message.reply_text('אנא הכנס מספר רכב תקין (8 ספרות):')

async def handle_pickup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    pickup_location = update.message.text.strip()
    
    TEMP_CAR_DATA[user_id]['pickup_location'] = pickup_location
    USER_STATES[user_id] = UserState.WAITING_DELIVERY
    
    await update.message.reply_text('איפה נמסר הרכב?')

async def handle_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    delivery_location = update.message.text.strip()
    
    TEMP_CAR_DATA[user_id]['delivery_location'] = delivery_location
    USER_STATES[user_id] = UserState.WAITING_NOTES
    
    await update.message.reply_text('הערות (אופציונלי):')

async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    notes = update.message.text.strip()
    
    TEMP_CAR_DATA[user_id]['notes'] = notes
    USER_STATES[user_id] = UserState.WAITING_JOB_TYPE
    
    await update.message.reply_text(
        'איזה משימה עשיתה?',
        reply_markup=get_job_type_keyboard()
    )

async def handle_job_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    job_type = update.message.text.strip()
    
    if job_type in JOB_TYPES.values():
        TEMP_CAR_DATA[user_id]['job_type'] = job_type
        
        # Save to database
        conn = sqlite3.connect('car_jobs.db')
        c = conn.cursor()
        
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M')
        
        c.execute('''INSERT INTO cars 
                     (car_number, pickup_location, delivery_location, notes, job_type, date, time, user_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (TEMP_CAR_DATA[user_id]['car_number'],
                   TEMP_CAR_DATA[user_id]['pickup_location'],
                   TEMP_CAR_DATA[user_id]['delivery_location'],
                   TEMP_CAR_DATA[user_id]['notes'],
                   job_type,
                   date_str,
                   time_str,
                   user_id))
        
        conn.commit()
        conn.close()
        
        USER_STATES[user_id] = UserState.MAIN_MENU
        
        await update.message.reply_text(
            f'✅ המשימה נשמרה בהצלחה!\n'
            f'רכב: {TEMP_CAR_DATA[user_id]["car_number"]}\n'
            f'שעה: {time_str}',
            reply_markup=get_main_keyboard()
        )
        
        # Clear temp data
        del TEMP_CAR_DATA[user_id]
    else:
        await update.message.reply_text(
            'אנא בחר סוג משימה מהאפשרויות:',
            reply_markup=get_job_type_keyboard()
        )

async def edit_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Get today's cars
    conn = sqlite3.connect('car_jobs.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    c.execute('''SELECT id, car_number, pickup_location, delivery_location, job_type, time
                 FROM cars WHERE user_id = ? AND date = ?
                 ORDER BY time''', (user_id, today))
    
    cars = c.fetchall()
    conn.close()
    
    if not cars:
        await update.message.reply_text(
            'אין משימות להיום לעריכה או מחיקה.',
            reply_markup=get_main_keyboard()
        )
        return
    
    keyboard = []
    message = "בחר משימה לעריכה/מחיקה:\n\n"
    
    for i, car in enumerate(cars, 1):
        car_id, car_number, pickup, delivery, job_type, time = car
        message += f"{i}. {car_number} ({time})\n   {pickup} → {delivery}\n   {job_type}\n\n"
        keyboard.append([InlineKeyboardButton(f"מחק משימה {i}", callback_data=f"delete_{car_id}")])
    
    keyboard.append([InlineKeyboardButton("חזור לתפריט", callback_data="back_to_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def monthly_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('car_jobs.db')
    c = conn.cursor()
    
    # Get stats for current month and 3 months back
    stats_message = "📊 סטטיסטיקה חודשית:\n\n"
    
    for months_back in range(4):  # Current month + 3 months back
        date = datetime.now() - timedelta(days=months_back*30)
        month_year = date.strftime('%Y-%m')
        month_name = date.strftime('%m/%Y')
        
        c.execute('''SELECT job_type, COUNT(*) FROM cars 
                     WHERE user_id = ? AND date LIKE ?
                     GROUP BY job_type''', (user_id, f"{month_year}%"))
        
        monthly_jobs = c.fetchall()
        
        if monthly_jobs:
            total = sum(count for _, count in monthly_jobs)
            stats_message += f"🗓️ {month_name} - סך הכל: {total}\n"
            
            for job_type, count in monthly_jobs:
                stats_message += f"   • {job_type}: {count}\n"
            stats_message += "\n"
    
    conn.close()
    
    if "סך הכל:" not in stats_message:
        stats_message += "אין נתונים להצגה."
    
    await update.message.reply_text(stats_message, reply_markup=get_main_keyboard())

async def end_of_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('car_jobs.db')
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get today's summary
    c.execute('''SELECT job_type, COUNT(*) FROM cars 
                 WHERE user_id = ? AND date = ?
                 GROUP BY job_type''', (user_id, today))
    
    job_counts = dict(c.fetchall())
    
    # Get all jobs for detailed report
    c.execute('''SELECT car_number, pickup_location, delivery_location, notes, job_type, time
                 FROM cars WHERE user_id = ? AND date = ?
                 ORDER BY time''', (user_id, today))
    
    all_jobs = c.fetchall()
    conn.close()
    
    total_jobs = sum(job_counts.values())
    
    if total_jobs == 0:
        await update.message.reply_text(
            'אין משימות להיום.',
            reply_markup=get_main_keyboard()
        )
        return
    
    # Create summary message
    summary = f"📋 סיכום יום {datetime.now().strftime('%d/%m/%Y')}\n\n"
    summary += f"סך כולל המשימות: {total_jobs}\n"
    
    for job_type in JOB_TYPES.values():
        count = job_counts.get(job_type, 0)
        job_name = job_type.replace('משימת ', 'משימות ')
        summary += f"{job_name}: {count}\n"
    
    summary += "\n" + "="*30 + "\n\n"
    
    # Add detailed jobs
    for i, job in enumerate(all_jobs, 1):
        car_number, pickup, delivery, notes, job_type, time = job
        summary += f"משימה {i}\n"
        summary += f"מספר רכב: {car_number}\n"
        summary += f"נאסף: {pickup}\n"
        summary += f"נמסר: {delivery}\n"
        summary += f"הערות: {notes if notes else 'ללא'}\n"
        summary += f"סוג משימה: {job_type}\n"
        summary += f"שעה: {time}\n"
        summary += "-" * 20 + "\n\n"
    
    # Store summary for email
    context.user_data['daily_summary'] = summary
    USER_STATES[user_id] = UserState.WAITING_EMAIL
    
    await update.message.reply_text(
        summary + "\nהאם לשלוח בדוא\"ל?",
        reply_markup=get_email_keyboard()
    )

async def handle_email_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    choice = update.message.text.strip()
    
    if choice == 'דלג':
        # Clear today's data
        conn = sqlite3.connect('car_jobs.db')
        c = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('DELETE FROM cars WHERE user_id = ? AND date = ?', (user_id, today))
        conn.commit()
        conn.close()
        
        USER_STATES[user_id] = UserState.MAIN_MENU
        await update.message.reply_text(
            '✅ יום עבודה הסתיים! הנתונים נמחקו.',
            reply_markup=get_main_keyboard()
        )
        
    elif choice == 'כן':
        await show_email_management(update, context)
    else:
        await update.message.reply_text(
            'אנא בחר "כן" או "דלג":',
            reply_markup=get_email_keyboard()
        )

async def show_email_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('car_jobs.db')
    c = conn.cursor()
    c.execute('SELECT email FROM emails WHERE user_id = ?', (user_id,))
    emails = [row[0] for row in c.fetchall()]
    conn.close()
    
    keyboard = []
    
    if emails:
        message = "📧 כתובות דוא\"ל:\n\n"
        for i, email in enumerate(emails, 1):
            message += f"{i}. {email}\n"
            keyboard.append([InlineKeyboardButton(f"מחק {email}", callback_data=f"del_email_{i-1}")])
        message += "\n"
    else:
        message = "אין כתובות דוא\"ל שמורות.\n\n"
    
    keyboard.extend([
        [InlineKeyboardButton("הוסף כתובת דוא\"ל", callback_data="add_email")],
        [InlineKeyboardButton("שלח דוא\"ל", callback_data="send_email")],
        [InlineKeyboardButton("חזור לתפריט", callback_data="back_to_menu")]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(message, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith('delete_'):
        car_id = int(data.split('_')[1])
        
        conn = sqlite3.connect('car_jobs.db')
        c = conn.cursor()
        c.execute('DELETE FROM cars WHERE id = ? AND user_id = ?', (car_id, user_id))
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            '✅ המשימה נמחקה בהצלחה!',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("חזור לתפריט", callback_data="back_to_menu")]])
        )
        
    elif data == 'back_to_menu':
        USER_STATES[user_id] = UserState.MAIN_MENU
        await query.edit_message_text('תפריט ראשי:')
        await context.bot.send_message(
            chat_id=user_id,
            text='בחר פעולה:',
            reply_markup=get_main_keyboard()
        )
        
    elif data == 'add_email':
        USER_STATES[user_id] = UserState.EMAIL_MANAGEMENT
        await query.edit_message_text('אנא הכנס כתובת דוא\"ל:')
        
    elif data == 'send_email':
        await send_daily_email(update, context, query)
        
    elif data.startswith('del_email_'):
        email_index = int(data.split('_')[2])
        
        conn = sqlite3.connect('car_jobs.db')
        c = conn.cursor()
        c.execute('SELECT email FROM emails WHERE user_id = ?', (user_id,))
        emails = [row[0] for row in c.fetchall()]
        
        if 0 <= email_index < len(emails):
            email_to_delete = emails[email_index]
            c.execute('DELETE FROM emails WHERE email = ? AND user_id = ?', (email_to_delete, user_id))
            conn.commit()
        
        conn.close()
        
        await show_email_management(update, context)

async def handle_email_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    email = update.message.text.strip()
    
    # Basic email validation
    if '@' in email and '.' in email:
        conn = sqlite3.connect('car_jobs.db')
        c = conn.cursor()
        
        try:
            c.execute('INSERT INTO emails (email, user_id) VALUES (?, ?)', (email, user_id))
            conn.commit()
            await update.message.reply_text(f'✅ כתובת הדוא\"ל {email} נוספה!')
        except sqlite3.IntegrityError:
            await update.message.reply_text('כתובת דוא\"ל זו כבר קיימת.')
        
        conn.close()
        await show_email_management(update, context)
    else:
        await update.message.reply_text('אנא הכנס כתובת דוא\"ל תקינה:')

async def send_daily_email(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('car_jobs.db')
    c = conn.cursor()
    c.execute('SELECT email FROM emails WHERE user_id = ?', (user_id,))
    emails = [row[0] for row in c.fetchall()]
    conn.close()
    
    if not emails:
        message = 'אין כתובות דוא\"ל שמורות. אנא הוסף כתובת דוא\"ל תחילה.'
        if query:
            await query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    summary = context.user_data.get('daily_summary', '')
    if not summary:
        message = 'אין נתונים לשליחה.'
        if query:
            await query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    try:
        # Send email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = ', '.join(emails)
        msg['Subject'] = f"סיכום יום עבודה - {datetime.now().strftime('%d/%m/%Y')}"
        
        msg.attach(MIMEText(summary, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        # Clear today's data after successful email
        conn = sqlite3.connect('car_jobs.db')
        c = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        c.execute('DELETE FROM cars WHERE user_id = ? AND date = ?', (user_id, today))
        conn.commit()
        conn.close()
        
        USER_STATES[user_id] = UserState.MAIN_MENU
        
        success_message = f'✅ דוא\"ל נשלח בהצלחה ל-{len(emails)} כתובות!\nיום עבודה הסתיים והנתונים נמחקו.'
        
        if query:
            await query.edit_message_text(success_message)
            await context.bot.send_message(
                chat_id=user_id,
                text='בחר פעולה:',
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                success_message,
                reply_markup=get_main_keyboard()
            )
            
    except Exception as e:
        error_message = f'❌ שגיאה בשליחת דוא\"ל: {str(e)}'
        if query:
            await query.edit_message_text(error_message)
        else:
            await update.message.reply_text(error_message)

def main():
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Run the bot
    application.run_polling()

if __name__ == '__main__':
    main()
