import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8195716721:AAGfrro7LCy1WTr4QccCZgtnIJvt3M6CdVI"
EMAIL_ADDRESS = "Avivpeten123456789@gmail.com"
EMAIL_PASSWORD = "ycqx xqaf xicz ywgi"

# Global storage for bot data
bot_data = {
    'today_tasks': [],
    'monthly_stats': {
        'שינוע': 0,
        'טרמפ': 0,
        'סרק': 0,
        'טסט': 0,
        'מוסך': 0
    },
    'email_list': [],
    'current_month': datetime.now().month,
    'current_year': datetime.now().year,
    'last_reset': datetime.now().date()
}

# User states
user_states = {}

class States:
    MAIN_MENU = "main_menu"
    WAITING_CAR_NUMBER = "waiting_car_number"
    WAITING_PICKUP = "waiting_pickup"
    WAITING_DROPOFF = "waiting_dropoff"
    WAITING_NOTES = "waiting_notes"
    WAITING_TASK_TYPE = "waiting_task_type"
    WAITING_EMAIL_ACTION = "waiting_email_action"
    WAITING_NEW_EMAIL = "waiting_new_email"
    WAITING_DELETE_EMAIL = "waiting_delete_email"
    EDIT_DELETE_MENU = "edit_delete_menu"
    WAITING_TASK_SELECT = "waiting_task_select"

def reset_monthly_data_if_needed():
    """Reset monthly data if it's a new month"""
    current_date = datetime.now()
    if (current_date.month != bot_data['current_month'] or 
        current_date.year != bot_data['current_year']):
        bot_data['monthly_stats'] = {
            'שינוע': 0,
            'טרמפ': 0,
            'סרק': 0,
            'טסט': 0,
            'מוסך': 0
        }
        bot_data['current_month'] = current_date.month
        bot_data['current_year'] = current_date.year

def reset_daily_data_if_needed():
    """Reset daily data if it's a new day"""
    today = datetime.now().date()
    if bot_data['last_reset'] != today:
        bot_data['today_tasks'] = []
        bot_data['last_reset'] = today

def format_car_number(car_number):
    """Format car number from 11111111 to 111-11-111"""
    if len(car_number) == 8 and car_number.isdigit():
        return f"{car_number[:3]}-{car_number[3:5]}-{car_number[5:]}"
    return car_number

def get_main_keyboard():
    """Get main menu keyboard"""
    keyboard = [
        [KeyboardButton("רכב הבא")],
        [KeyboardButton("סיום יום")],
        [KeyboardButton("עריכה/מחיקה")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_task_type_keyboard():
    """Get task type selection keyboard"""
    keyboard = [
        [KeyboardButton("משימת שינוע")],
        [KeyboardButton("משימת טרמפ")],
        [KeyboardButton("משימת סרק")],
        [KeyboardButton("משימת טסט")],
        [KeyboardButton("משימת מוסך")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    reset_monthly_data_if_needed()
    reset_daily_data_if_needed()
    
    user_id = update.effective_user.id
    user_states[user_id] = States.MAIN_MENU
    
    welcome_message = "ברוך הבא לבוט מעקב רכבים!\nבחר אפשרות:"
    await update.message.reply_text(
        welcome_message, 
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all text messages"""
    reset_monthly_data_if_needed()
    reset_daily_data_if_needed()
    
    user_id = update.effective_user.id
    text = update.message.text
    state = user_states.get(user_id, States.MAIN_MENU)
    
    # Main menu options
    if text == "רכב הבא":
        user_states[user_id] = States.WAITING_CAR_NUMBER
        context.user_data['current_task'] = {}
        await update.message.reply_text(
            "הזן מספר רכב (8 ספרות):",
            reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
        )
        return
    
    elif text == "עריכה/מחיקה":
        await show_edit_delete_menu(update, context)
        return
        
    elif text == "סיום יום":
        await handle_end_of_day(update, context)
        return
    
    # Handle states
    if state == States.WAITING_CAR_NUMBER:
        await handle_car_number(update, context)
    elif state == States.WAITING_PICKUP:
        await handle_pickup_location(update, context)
    elif state == States.WAITING_DROPOFF:
        await handle_dropoff_location(update, context)
    elif state == States.WAITING_NOTES:
        await handle_notes(update, context)
    elif state == States.WAITING_TASK_TYPE:
        await handle_task_type(update, context)
    elif state == States.WAITING_NEW_EMAIL:
        await handle_new_email(update, context)
    elif state == States.WAITING_DELETE_EMAIL:
        await handle_delete_email(update, context)
    elif state == States.WAITING_TASK_SELECT:
        await handle_task_selection(update, context)

async def handle_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle car number input"""
    user_id = update.effective_user.id
    car_number = update.message.text.strip()
    
    if len(car_number) == 8 and car_number.isdigit():
        formatted_number = format_car_number(car_number)
        context.user_data['current_task']['car_number'] = formatted_number
        user_states[user_id] = States.WAITING_PICKUP
        await update.message.reply_text(f"מספר רכב: {formatted_number}\nמאיפה לאסוף את הרכב?")
    else:
        await update.message.reply_text("אנא הזן מספר רכב תקין (8 ספרות):")

async def handle_pickup_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pickup location input"""
    user_id = update.effective_user.id
    pickup = update.message.text.strip()
    
    context.user_data['current_task']['pickup'] = pickup
    user_states[user_id] = States.WAITING_DROPOFF
    await update.message.reply_text("לאן להוביל את הרכב?")

async def handle_dropoff_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dropoff location input"""
    user_id = update.effective_user.id
    dropoff = update.message.text.strip()
    
    context.user_data['current_task']['dropoff'] = dropoff
    user_states[user_id] = States.WAITING_NOTES
    await update.message.reply_text("הערות (או לחץ /skip לדלג):")

async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle notes input"""
    user_id = update.effective_user.id
    notes = update.message.text.strip()
    
    if notes.lower() == "/skip":
        notes = ""
    
    context.user_data['current_task']['notes'] = notes
    user_states[user_id] = States.WAITING_TASK_TYPE
    await update.message.reply_text(
        "בחר סוג משימה:", 
        reply_markup=get_task_type_keyboard()
    )

async def handle_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle task type selection"""
    user_id = update.effective_user.id
    task_type = update.message.text.strip()
    
    task_map = {
        "משימת שינוע": "שינוע",
        "משימת טרמפ": "טרמפ", 
        "משימת סרק": "סרק",
        "משימת טסט": "טסט",
        "משימת מוסך": "מוסך"
    }
    
    if task_type in task_map:
        task_key = task_map[task_type]
        context.user_data['current_task']['task_type'] = task_key
        context.user_data['current_task']['timestamp'] = datetime.now()
        
        # Add to today's tasks
        bot_data['today_tasks'].append(context.user_data['current_task'].copy())
        
        # Update monthly stats
        bot_data['monthly_stats'][task_key] += 1
        
        # Show summary
        task = context.user_data['current_task']
        summary = f"""✅ משימה נוספה בהצלחה!

🚗 רכב: {task['car_number']}
📍 איסוף: {task['pickup']}
📍 הובלה: {task['dropoff']}
📝 הערות: {task['notes'] if task['notes'] else 'ללא'}
🔧 סוג משימה: {task_type}
⏰ זמן: {task['timestamp'].strftime('%H:%M')}"""
        
        user_states[user_id] = States.MAIN_MENU
        await update.message.reply_text(summary, reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("אנא בחר סוג משימה תקין:")

async def show_edit_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show edit/delete menu with today's tasks"""
    user_id = update.effective_user.id
    
    if not bot_data['today_tasks']:
        await update.message.reply_text(
            "אין משימות להיום.",
            reply_markup=get_main_keyboard()
        )
        return
    
    message = "בחר משימה לעריכה/מחיקה:\n\n"
    for i, task in enumerate(bot_data['today_tasks'], 1):
        message += f"{i}. רכב {task['car_number']} - {task['task_type']} ({task['timestamp'].strftime('%H:%M')})\n"
    
    message += "\nהזן מספר המשימה או /cancel לביטול:"
    
    user_states[user_id] = States.WAITING_TASK_SELECT
    await update.message.reply_text(
        message,
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )

async def handle_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle task selection for edit/delete"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text.lower() == "/cancel":
        user_states[user_id] = States.MAIN_MENU
        await update.message.reply_text("בוטל.", reply_markup=get_main_keyboard())
        return
    
    try:
        task_num = int(text) - 1
        if 0 <= task_num < len(bot_data['today_tasks']):
            task = bot_data['today_tasks'][task_num]
            
            keyboard = [
                [InlineKeyboardButton("מחק", callback_data=f"delete_{task_num}")],
                [InlineKeyboardButton("ביטול", callback_data="cancel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            task_info = f"""📋 פרטי המשימה:
🚗 רכב: {task['car_number']}
📍 איסוף: {task['pickup']}
📍 הובלה: {task['dropoff']}
📝 הערות: {task['notes'] if task['notes'] else 'ללא'}
🔧 סוג: {task['task_type']}
⏰ זמן: {task['timestamp'].strftime('%H:%M')}

מה תרצה לעשות?"""
            
            await update.message.reply_text(task_info, reply_markup=reply_markup)
        else:
            await update.message.reply_text("מספר משימה לא תקין. נסה שוב:")
    except ValueError:
        await update.message.reply_text("אנא הזן מספר תקין או /cancel לביטול:")

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("delete_"):
        task_num = int(data.split("_")[1])
        deleted_task = bot_data['today_tasks'].pop(task_num)
        
        # Update monthly stats
        bot_data['monthly_stats'][deleted_task['task_type']] -= 1
        
        await query.edit_message_text("✅ המשימה נמחקה בהצלחה!")
        user_states[user_id] = States.MAIN_MENU
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="חזרה לתפריט הראשי:",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "cancel":
        await query.edit_message_text("בוטל.")
        user_states[user_id] = States.MAIN_MENU
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="חזרה לתפריט הראשי:",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "send_email":
        await send_daily_summary_email(query, context)
    
    elif data == "skip_email":
        user_states[user_id] = States.MAIN_MENU
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="חזרה לתפריט הראשי:",
            reply_markup=get_main_keyboard()
        )
    
    elif data == "manage_emails":
        await show_email_management(query, context)
    
    elif data.startswith("email_"):
        await handle_email_management_callback(query, context)

async def handle_end_of_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle end of day summary"""
    user_id = update.effective_user.id
    
    # Today's summary
    today_count = len(bot_data['today_tasks'])
    today_by_type = {}
    
    for task in bot_data['today_tasks']:
        task_type = task['task_type']
        today_by_type[task_type] = today_by_type.get(task_type, 0) + 1
    
    # Monthly summary
    monthly_total = sum(bot_data['monthly_stats'].values())
    
    summary = f"""📊 סיכום יומי - {datetime.now().strftime('%d/%m/%Y')}

🚗 סך הכל משימות היום: {today_count}
"""
    
    if today_by_type:
        summary += "\n📋 פירוט משימות היום:\n"
        for task_type, count in today_by_type.items():
            summary += f"• משימות {task_type}: {count}\n"
    
    summary += f"""

📈 סיכום חודשי - {datetime.now().strftime('%m/%Y')}
🚗 סך כולל המשימות החודש: {monthly_total}

📋 פירוט חודשי:
• משימות שינוע: {bot_data['monthly_stats']['שינוע']}
• משימות טרמפ: {bot_data['monthly_stats']['טרמפ']}
• משימות סרק: {bot_data['monthly_stats']['סרק']}
• משימות מוסך: {bot_data['monthly_stats']['מוסך']}
• משימות טסט: {bot_data['monthly_stats']['טסט']}"""
    
    keyboard = [
        [InlineKeyboardButton("נהל כתובות מייל", callback_data="manage_emails")],
        [InlineKeyboardButton("שלח מייל עם סיכום היום", callback_data="send_email")],
        [InlineKeyboardButton("דלג", callback_data="skip_email")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(summary, reply_markup=reply_markup)
    
    # Reset today's tasks after end of day
    bot_data['today_tasks'] = []

async def show_email_management(query, context: ContextTypes.DEFAULT_TYPE):
    """Show email management options"""
    user_id = query.from_user.id
    
    if not bot_data['email_list']:
        message = "רשימת מיילים ריקה.\nהזן כתובת מייל חדשה או /cancel לביטול:"
        user_states[user_id] = States.WAITING_NEW_EMAIL
        await query.edit_message_text(message)
        return
    
    message = "כתובות מייל נוכחיות:\n\n"
    for i, email in enumerate(bot_data['email_list'], 1):
        message += f"{i}. {email}\n"
    
    keyboard = [
        [InlineKeyboardButton("הוסף מייל", callback_data="email_add")],
        [InlineKeyboardButton("מחק מייל", callback_data="email_delete")],
        [InlineKeyboardButton("חזור", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)

async def handle_email_management_callback(query, context: ContextTypes.DEFAULT_TYPE):
    """Handle email management callbacks"""
    user_id = query.from_user.id
    action = query.data.split("_")[1]
    
    if action == "add":
        user_states[user_id] = States.WAITING_NEW_EMAIL
        await query.edit_message_text("הזן כתובת מייל חדשה או /cancel לביטול:")
    
    elif action == "delete":
        if not bot_data['email_list']:
            await query.edit_message_text("אין כתובות מייל למחיקה.")
            return
            
        user_states[user_id] = States.WAITING_DELETE_EMAIL
        message = "בחר מייל למחיקה (הזן מספר) או /cancel לביטול:\n\n"
        for i, email in enumerate(bot_data['email_list'], 1):
            message += f"{i}. {email}\n"
        await query.edit_message_text(message)

async def handle_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new email input"""
    user_id = update.effective_user.id
    email = update.message.text.strip()
    
    if email.lower() == "/cancel":
        user_states[user_id] = States.MAIN_MENU
        await update.message.reply_text("בוטל.", reply_markup=get_main_keyboard())
        return
    
    # Simple email validation
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        if email not in bot_data['email_list']:
            bot_data['email_list'].append(email)
            await update.message.reply_text(f"✅ המייל {email} נוסף בהצלחה!")
        else:
            await update.message.reply_text("המייל כבר קיים ברשימה.")
    else:
        await update.message.reply_text("כתובת מייל לא תקינה. נסה שוב:")
        return
    
    user_states[user_id] = States.MAIN_MENU
    await update.message.reply_text("חזרה לתפריט הראשי:", reply_markup=get_main_keyboard())

async def handle_delete_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email deletion"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if text.lower() == "/cancel":
        user_states[user_id] = States.MAIN_MENU
        await update.message.reply_text("בוטל.", reply_markup=get_main_keyboard())
        return
    
    try:
        index = int(text) - 1
        if 0 <= index < len(bot_data['email_list']):
            deleted_email = bot_data['email_list'].pop(index)
            await update.message.reply_text(f"✅ המייל {deleted_email} נמחק בהצלחה!")
        else:
            await update.message.reply_text("מספר לא תקין. נסה שוב:")
            return
    except ValueError:
        await update.message.reply_text("אנא הזן מספר תקין או /cancel לביטול:")
        return
    
    user_states[user_id] = States.MAIN_MENU
    await update.message.reply_text("חזרה לתפריט הראשי:", reply_markup=get_main_keyboard())

async def send_daily_summary_email(query, context: ContextTypes.DEFAULT_TYPE):
    """Send daily summary via email"""
    user_id = query.from_user.id
    
    if not bot_data['email_list']:
        await query.edit_message_text("אין כתובות מייל ברשימה. הוסף כתובות קודם.")
        return
    
    try:
        # Prepare email content
        today_date = datetime.now().strftime('%d/%m/%Y')
        subject = f"סיכום יומי - {today_date}"
        
        # Create detailed task list
        body = f"סיכום רכבים ליום {today_date}\n\n"
        
        if bot_data['today_tasks']:
            body += "רשימת משימות:\n"
            body += "=" * 50 + "\n"
            
            for i, task in enumerate(bot_data['today_tasks'], 1):
                body += f"{i}. רכב {task['car_number']}\n"
                body += f"   איסוף: {task['pickup']}\n"
                body += f"   הובלה: {task['dropoff']}\n"
                body += f"   סוג משימה: {task['task_type']}\n"
                body += f"   זמן: {task['timestamp'].strftime('%H:%M')}\n"
                if task['notes']:
                    body += f"   הערות: {task['notes']}\n"
                body += "-" * 30 + "\n"
            
            # Summary by type
            today_by_type = {}
            for task in bot_data['today_tasks']:
                task_type = task['task_type']
                today_by_type[task_type] = today_by_type.get(task_type, 0) + 1
            
            body += f"\nסיכום לפי סוג משימה:\n"
            for task_type, count in today_by_type.items():
                body += f"• משימות {task_type}: {count}\n"
        else:
            body += "לא בוצעו משימות היום.\n"
        
        # Monthly summary
        monthly_total = sum(bot_data['monthly_stats'].values())
        body += f"\n\nסיכום חודשי - {datetime.now().strftime('%m/%Y')}:\n"
        body += f"סך כולל המשימות: {monthly_total}\n"
        for task_type, count in bot_data['monthly_stats'].items():
            body += f"• משימות {task_type}: {count}\n"
        
        # Send email
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        
        success_count = 0
        for email in bot_data['email_list']:
            try:
                msg['To'] = email
                server.send_message(msg)
                success_count += 1
                del msg['To']
            except Exception as e:
                logger.error(f"Failed to send email to {email}: {e}")
        
        server.quit()
        
        await query.edit_message_text(f"✅ הסיכום נשלח בהצלחה ל-{success_count} כתובות!")
        
    except Exception as e:
        logger.error(f"Email sending failed: {e}")
        await query.edit_message_text("❌ שליחת המייל נכשלה. בדוק את ההגדרות.")
    
    user_states[user_id] = States.MAIN_MENU
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="חזרה לתפריט הראשי:",
        reply_markup=get_main_keyboard()
    )

def main():
    """Start the bot"""
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Start the bot
    print("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
