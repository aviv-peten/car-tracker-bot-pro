import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import os
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

# Simple file-based storage
STORAGE_FILE = 'bot_data.json'

def load_data():
    """Load data from file"""
    try:
        if os.path.exists(STORAGE_FILE):
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading data: {e}")
    
    return {
        'user_data': {},
        'monthly_stats': {},
        'email_lists': {}
    }

def save_data(data):
    """Save data to file"""
    try:
        with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

# Load initial data
storage = load_data()
user_data = storage.get('user_data', {})
monthly_stats = storage.get('monthly_stats', {})
email_lists = storage.get('email_lists', {})

def get_user_data(user_id):
    user_id = str(user_id)
    if user_id not in user_data:
        user_data[user_id] = {
            'current_job': {},
            'daily_jobs': [],
            'state': 'main_menu',
            'temp_car_number': '',
            'edit_job_index': -1
        }
    return user_data[user_id]

def get_monthly_stats(user_id):
    user_id = str(user_id)
    if user_id not in monthly_stats:
        monthly_stats[user_id] = {}
    return monthly_stats[user_id]

def get_email_list(user_id):
    user_id = str(user_id)
    if user_id not in email_lists:
        email_lists[user_id] = []
    return email_lists[user_id]

def save_all_data():
    """Save all data to file"""
    storage_data = {
        'user_data': user_data,
        'monthly_stats': monthly_stats,
        'email_lists': email_lists
    }
    save_data(storage_data)

def format_car_number(number_str):
    """Format 8-digit car number to XXX-XX-XXX"""
    if len(number_str) == 8:
        return f"{number_str[:3]}-{number_str[3:5]}-{number_str[5:]}"
    return number_str

def create_number_keyboard():
    """Create keyboard for car number input"""
    keyboard = []
    # Numbers 1-9, 0
    for i in range(1, 10):
        if (i-1) % 3 == 0:
            keyboard.append([])
        keyboard[-1].append(InlineKeyboardButton(str(i), callback_data=f"num_{i}"))
    
    keyboard.append([InlineKeyboardButton("0", callback_data="num_0")])
    
    # Control buttons
    keyboard.append([
        InlineKeyboardButton("❌ מחק", callback_data="num_delete"),
        InlineKeyboardButton("✅ אישור", callback_data="num_confirm")
    ])
    keyboard.append([InlineKeyboardButton("🔙 חזור לתפריט", callback_data="back_to_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def create_main_menu():
    """Create main menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("🚗 רכב חדש", callback_data="new_car")],
        [InlineKeyboardButton("📊 סיום יום", callback_data="end_day")],
        [InlineKeyboardButton("✏️ עריכה/מחיקה", callback_data="edit_delete")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_job_type_keyboard():
    """Create job type selection keyboard"""
    keyboard = []
    icons = ['🚚', '🔄', '👥', '🔧', '🧪']
    job_keys = list(JOB_TYPES.keys())
    
    for i, (key, value) in enumerate(JOB_TYPES.items()):
        icon = icons[i] if i < len(icons) else '📋'
        keyboard.append([InlineKeyboardButton(f"{icon} {value}", callback_data=f"job_{key}")])
    
    keyboard.append([InlineKeyboardButton("🔙 חזור", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)

def create_yes_no_keyboard():
    """Create yes/no keyboard"""
    keyboard = [
        [InlineKeyboardButton("✅ כן", callback_data="yes")],
        [InlineKeyboardButton("⏭️ דלג", callback_data="no")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    data['state'] = 'main_menu'
    data['temp_car_number'] = ''  # Clear any previous temp number
    save_all_data()
    
    welcome_msg = "🚗 ברוך הבא למערכת מעקב רכבים!\n\n"
    welcome_msg += "בחר פעולה מהתפריט:"
    
    await update.message.reply_text(
        welcome_msg,
        reply_markup=create_main_menu()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    callback_data = query.data
    
    try:
        # Main menu handlers
        if callback_data == "new_car":
            data['state'] = 'car_number'
            data['current_job'] = {}
            data['temp_car_number'] = ''  # RESET temp number when starting new car
            save_all_data()
            await query.edit_message_text(
                "🚗 הכנס מספר רכב (8 ספרות):\n\n" +
                f"מספר נוכחי: {'_'*8}",
                reply_markup=create_number_keyboard()
            )
        
        elif callback_data == "end_day":
            await handle_end_day(query, user_id)
        
        elif callback_data == "edit_delete":
            await handle_edit_delete(query, user_id)
        
        elif callback_data == "back_to_menu":
            data['state'] = 'main_menu'
            data['temp_car_number'] = ''  # CLEAR temp number when going back
            save_all_data()
            await query.edit_message_text(
                "🚗 בחר פעולה מהתפריט:",
                reply_markup=create_main_menu()
            )
        
        # Number input handlers
        elif callback_data.startswith("num_"):
            await handle_number_input(query, user_id, callback_data)
        
        # Job type handlers
        elif callback_data.startswith("job_"):
            job_type = callback_data.replace("job_", "")
            data['current_job']['job_type'] = job_type
            data['current_job']['timestamp'] = datetime.now().isoformat()
            
            # Save the job
            data['daily_jobs'].append(data['current_job'].copy())
            job_name = JOB_TYPES[job_type]
            car_num = data['current_job']['car_number']
            
            success_msg = "✅ המשימה נשמרה בהצלחה!\n\n"
            success_msg += f"🚗 רכב: {car_num}\n"
            success_msg += f"📋 סוג משימה: {job_name}\n"
            success_msg += f"📍 איסוף: {data['current_job'].get('pickup', 'לא צוין')}\n"
            success_msg += f"📍 הורדה: {data['current_job'].get('dropoff', 'לא צוין')}\n"
            if data['current_job'].get('notes'):
                success_msg += f"📝 הערות: {data['current_job']['notes']}\n"
            success_msg += "\nבחר פעולה נוספת:"
            
            await query.edit_message_text(
                success_msg,
                reply_markup=create_main_menu()
            )
            data['state'] = 'main_menu'
            data['temp_car_number'] = ''  # CLEAR temp number after job completion
            save_all_data()
        
        # Email handlers
        elif callback_data in ["yes", "no"]:
            if callback_data == "yes":
                await handle_email_selection(query, user_id)
            else:
                data['state'] = 'main_menu'
                await query.edit_message_text(
                    "📊 סיום יום הושלם!\n\nבחר פעולה:",
                    reply_markup=create_main_menu()
                )
        
        # Edit/Delete handlers
        elif callback_data.startswith("edit_"):
            job_index = int(callback_data.replace("edit_", ""))
            data['edit_job_index'] = job_index
            await handle_job_edit(query, user_id, job_index)
        
        elif callback_data.startswith("delete_"):
            job_index = int(callback_data.replace("delete_", ""))
            if 0 <= job_index < len(data['daily_jobs']):
                deleted_job = data['daily_jobs'].pop(job_index)
                await query.edit_message_text(
                    f"🗑️ המשימה נמחקה!\n"
                    f"רכב: {deleted_job['car_number']}\n"
                    f"סוג: {JOB_TYPES[deleted_job['job_type']]}"
                )
                save_all_data()
                await handle_edit_delete(query, user_id)
    
    except Exception as e:
        logger.error(f"Error in button_callback: {e}")
        await query.edit_message_text(
            f"❌ שגיאה: {str(e)}\n\nבחר פעולה:",
            reply_markup=create_main_menu()
        )

async def handle_number_input(query, user_id, callback_data):
    """Handle number input for car number - COMPLETELY FIXED VERSION"""
    data = get_user_data(user_id)
    
    # Ensure temp_car_number is initialized
    if 'temp_car_number' not in data:
        data['temp_car_number'] = ''
    
    # Handle different button presses
    if callback_data == "num_delete":
        # Delete last digit
        if data['temp_car_number']:
            data['temp_car_number'] = data['temp_car_number'][:-1]
        
    elif callback_data == "num_confirm":
        # Confirm number input
        if len(data['temp_car_number']) == 8:
            formatted_number = format_car_number(data['temp_car_number'])
            data['current_job']['car_number'] = formatted_number
            data['state'] = 'pickup_location'
            # DON'T clear temp_car_number here - wait until job is complete
            save_all_data()
            await query.edit_message_text("📍 הכנס מיקום איסוף:")
            return
        else:
            # Show error for incomplete number
            remaining = 8 - len(data['temp_car_number'])
            display_text = data['temp_car_number'] + ('_' * remaining)
            
            await query.edit_message_text(
                f"❌ מספר רכב חייב להיות 8 ספרות!\n"
                f"נוכחי: {len(data['temp_car_number'])} ספרות\n"
                f"נותרו: {remaining} ספרות\n\n"
                f"מספר נוכחי: {display_text}",
                reply_markup=create_number_keyboard()
            )
            save_all_data()
            return
    
    else:
        # Add number digit
        number = callback_data.replace("num_", "")
        if len(data['temp_car_number']) < 8:
            data['temp_car_number'] += number
        else:
            # If already 8 digits, don't add more
            pass
    
    # Update display with current number
    current_number = data['temp_car_number']
    remaining = 8 - len(current_number)
    
    # Create display string
    if len(current_number) == 8:
        display_text = format_car_number(current_number)
    else:
        display_text = current_number + ('_' * remaining)
    
    # Status message
    status_msg = f"🚗 הכנס מספר רכב (8 ספרות):\n\n"
    status_msg += f"מספר נוכחי: {display_text}\n"
    if remaining > 0:
        status_msg += f"נותרו: {remaining} ספרות"
    else:
        status_msg += "✅ מוכן לאישור!"
    
    # Save data before updating message
    save_all_data()
    
    # Update the message
    await query.edit_message_text(
        status_msg,
        reply_markup=create_number_keyboard()
    )

async def handle_end_day(query, user_id):
    """Handle end of day statistics"""
    data = get_user_data(user_id)
    jobs = data['daily_jobs']
    
    if not jobs:
        await query.edit_message_text(
            "📊 אין משימות להיום\n\nבחר פעולה:",
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
    for job_type, count in job_counts.items():
        stats[today]['job_types'][job_type] = stats[today]['job_types'].get(job_type, 0) + count
    
    # Create summary
    today_date = datetime.now().strftime("%d/%m/%Y")
    summary = f"📊 סיכום יום - {today_date}\n\n"
    summary += f"🔢 סה\"כ משימות: {total_jobs}\n\n"
    
    icons = {'transport': '🚚', 'empty': '🔄', 'hitchhike': '👥', 'garage': '🔧', 'test': '🧪'}
    for job_type, count in job_counts.items():
        job_name = JOB_TYPES[job_type]
        icon = icons.get(job_type, '📋')
        summary += f"{icon} {job_name}: {count}\n"
    
    summary += f"\n📈 סטטיסטיקות חודשיות:\n"
    summary += f"📅 ימי עבודה החודש: {stats[today]['total_days']}\n"
    summary += f"🔢 סה\"כ משימות החודש: {stats[today]['total_jobs']}\n\n"
    
    summary += "📧 לשלוח דו\"ח במייל?"
    
    await query.edit_message_text(summary, reply_markup=create_yes_no_keyboard())
    save_all_data()

async def handle_email_selection(query, user_id):
    """Handle email selection and sending"""
    data = get_user_data(user_id)
    jobs = data['daily_jobs']
    
    if not jobs:
        await query.edit_message_text(
            "❌ אין משימות לשליחה\n\nבחר פעולה:",
            reply_markup=create_main_menu()
        )
        return
    
    try:
        # Create email content
        today = datetime.now().strftime("%d/%m/%Y")
        email_content = f"דו\"ח יומי - {today}\n"
        email_content += "=" * 30 + "\n\n"
        
        total_jobs = len(jobs)
        job_counts = Counter([job['job_type'] for job in jobs])
        
        email_content += f"סה\"כ משימות: {total_jobs}\n\n"
        
        for job_type, count in job_counts.items():
            job_name = JOB_TYPES[job_type]
            email_content += f"{job_name}: {count}\n"
        
        email_content += "\n" + "=" * 30 + "\n"
        email_content += "פירוט משימות:\n\n"
        
        for i, job in enumerate(jobs, 1):
            job_name = JOB_TYPES[job['job_type']]
            email_content += f"{i}. רכב {job['car_number']} - {job_name}\n"
            email_content += f"   איסוף: {job.get('pickup', 'לא צוין')}\n"
            email_content += f"   הורדה: {job.get('dropoff', 'לא צוין')}\n"
            if job.get('notes'):
                email_content += f"   הערות: {job['notes']}\n"
            email_content += "\n"
        
        # Send email
        await send_email(f"דו\"ח יומי - {today}", email_content, [EMAIL_USER])
        
        # Clear daily data after successful email send
        data['daily_jobs'] = []
        data['state'] = 'main_menu'
        data['temp_car_number'] = ''  # CLEAR temp number after email send
        
        await query.edit_message_text(
            "✅ הדו\"ח נשלח בהצלחה!\n"
            "🗑️ המידע היומי נמחק.\n\n"
            "בחר פעולה:",
            reply_markup=create_main_menu()
        )
        save_all_data()
        
    except Exception as e:
        logger.error(f"Email error: {e}")
        await query.edit_message_text(
            f"❌ שגיאה בשליחת המייל:\n{str(e)}\n\nבחר פעולה:",
            reply_markup=create_main_menu()
        )

async def send_email(subject, body, recipients):
    """Send email using SMTP"""
    try:
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
        logger.info(f"Email sent successfully to {recipients}")
        
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise

async def handle_edit_delete(query, user_id):
    """Handle edit/delete menu"""
    data = get_user_data(user_id)
    jobs = data['daily_jobs']
    
    if not jobs:
        await query.edit_message_text(
            "📝 אין משימות לעריכה היום\n\nבחר פעולה:",
            reply_markup=create_main_menu()
        )
        return
    
    keyboard = []
    for i, job in enumerate(jobs):
        job_name = JOB_TYPES[job['job_type']]
        car_num = job['car_number']
        keyboard.append([
            InlineKeyboardButton(f"✏️ {car_num} - {job_name}", callback_data=f"edit_{i}"),
            InlineKeyboardButton("🗑️", callback_data=f"delete_{i}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 חזור לתפריט הראשי", callback_data="back_to_menu")])
    
    await query.edit_message_text(
        "📝 בחר משימה לעריכה או מחיקה:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_job_edit(query, user_id, job_index):
    """Handle individual job editing"""
    data = get_user_data(user_id)
    if job_index >= len(data['daily_jobs']):
        await query.edit_message_text("❌ משימה לא נמצאה")
        return
        
    job = data['daily_jobs'][job_index]
    
    job_name = JOB_TYPES[job['job_type']]
    job_details = f"✏️ עריכת משימה:\n\n"
    job_details += f"🚗 רכב: {job['car_number']}\n"
    job_details += f"📋 סוג: {job_name}\n"
    job_details += f"📍 איסוף: {job.get('pickup', 'לא צוין')}\n"
    job_details += f"📍 הורדה: {job.get('dropoff', 'לא צוין')}\n"
    job_details += f"📝 הערות: {job.get('notes', 'אין')}\n\n"
    job_details += "איזה פרט תרצה לערוך?"
    
    keyboard = [
        [InlineKeyboardButton("📍 מיקום איסוף", callback_data="edit_pickup")],
        [InlineKeyboardButton("📍 מיקום הורדה", callback_data="edit_dropoff")],
        [InlineKeyboardButton("📝 הערות", callback_data="edit_notes")],
        [InlineKeyboardButton("📋 סוג משימה", callback_data="edit_job_type")],
        [InlineKeyboardButton("🔙 חזור", callback_data="edit_delete")]
    ]
    
    await query.edit_message_text(job_details, reply_markup=InlineKeyboardMarkup(keyboard))

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id
    data = get_user_data(user_id)
    text = update.message.text.strip()
    
    try:
        if data['state'] == 'pickup_location':
            data['current_job']['pickup'] = text
            data['state'] = 'dropoff_location'
            await update.message.reply_text("📍 הכנס מיקום הורדה:")
        
        elif data['state'] == 'dropoff_location':
            data['current_job']['dropoff'] = text
            data['state'] = 'notes'
            await update.message.reply_text("📝 הכנס הערות (או כל טקסט לדילוג):")
        
        elif data['state'] == 'notes':
            data['current_job']['notes'] = text
            data['state'] = 'job_type'
            await update.message.reply_text(
                "📋 בחר סוג משימה:",
                reply_markup=create_job_type_keyboard()
            )
        
        else:
            # Default response for unexpected messages
            await update.message.reply_text(
                "🚗 ברוך הבא למערכת מעקב רכבים!\n\nבחר פעולה:",
                reply_markup=create_main_menu()
            )
            data['state'] = 'main_menu'
            data['temp_car_number'] = ''  # CLEAR temp number on unexpected state
        
        save_all_data()
        
    except Exception as e:
        logger.error(f"Error in message_handler: {e}")
        await update.message.reply_text(
            f"❌ שגיאה: {str(e)}\n\nבחר פעולה:",
            reply_markup=create_main_menu()
        )

def main():
    """Main function"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        logger.info("Starting bot with polling...")
        
        # Start polling instead of webhook for Railway
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()
