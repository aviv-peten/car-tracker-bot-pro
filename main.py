import os
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Bot configuration
BOT_TOKEN = "8195716721:AAGfrro7LCy1WTr4QccCZgtnIJvt3M6CdVI"
EMAIL = "Avivpeten123456789@gmail.com"
EMAIL_PASSWORD = "ycqx xqaf xicz ywgi"

# Israel timezone
IST = pytz.timezone('Asia/Jerusalem')

class CarTrackerBot:
    def __init__(self):
        self.data_file = "car_data.json"
        self.load_data()
    
    def load_data(self):
        """Load data from JSON file"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
        except FileNotFoundError:
            self.data = {
                "daily_jobs": {},
                "monthly_stats": {},
                "emails": ["Avivpeten123456789@gmail.com"]
            }
            self.save_data()
    
    def save_data(self):
        """Save data to JSON file"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_today_key(self):
        """Get today's date key"""
        return datetime.now(IST).strftime("%Y-%m-%d")
    
    def get_month_key(self):
        """Get current month key"""
        return datetime.now(IST).strftime("%Y-%m")
    
    def cleanup_old_data(self):
        """Remove data older than 3 months"""
        cutoff_date = datetime.now(IST) - timedelta(days=90)
        cutoff_key = cutoff_date.strftime("%Y-%m")
        
        # Clean monthly stats
        months_to_remove = []
        for month in self.data["monthly_stats"]:
            if month < cutoff_key:
                months_to_remove.append(month)
        
        for month in months_to_remove:
            del self.data["monthly_stats"][month]
        
        self.save_data()

bot_instance = CarTrackerBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - show main menu"""
    keyboard = [
        [InlineKeyboardButton("🚗 רכב חדש", callback_data="new_car")],
        [InlineKeyboardButton("📊 סיום יום", callback_data="end_day")],
        [InlineKeyboardButton("✏️ עריכה/מחיקה", callback_data="edit_delete")],
        [InlineKeyboardButton("📧 ניהול מיילים", callback_data="manage_emails")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "ברוך הבא למעקב רכבים! 🚗\nבחר פעולה:",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "ברוך הבא למעקב רכבים! 🚗\nבחר פעולה:",
            reply_markup=reply_markup
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "new_car":
        await new_car_start(update, context)
    elif query.data == "end_day":
        await end_day(update, context)
    elif query.data == "edit_delete":
        await edit_delete(update, context)
    elif query.data == "manage_emails":
        await manage_emails(update, context)
    elif query.data == "back_main":
        await start(update, context)
    elif query.data.startswith("job_type_"):
        await handle_job_type(update, context)
    elif query.data.startswith("edit_job_"):
        await handle_edit_job(update, context)
    elif query.data.startswith("delete_job_"):
        await handle_delete_job(update, context)
    elif query.data == "send_email_yes":
        await send_daily_email(update, context)
    elif query.data == "send_email_no":
        await query.edit_message_text("סיום יום הושלם! ✅\nהנתונים נשמרו.")
        await start(update, context)
    elif query.data.startswith("email_"):
        await handle_email_selection(update, context)

async def new_car_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start new car entry"""
    context.user_data["state"] = "waiting_car_number"
    await update.callback_query.edit_message_text(
        "🚗 רכב חדש\n\nהזן מספר רכב (8 ספרות):"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages based on state"""
    state = context.user_data.get("state")
    
    if state == "waiting_car_number":
        await handle_car_number(update, context)
    elif state == "waiting_pickup":
        await handle_pickup_location(update, context)
    elif state == "waiting_dropoff":
        await handle_dropoff_location(update, context)
    elif state == "waiting_notes":
        await handle_notes(update, context)
    elif state == "waiting_email":
        await handle_new_email(update, context)

async def handle_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle car number input"""
    car_number = update.message.text.strip()
    
    if len(car_number) != 8 or not car_number.isdigit():
        await update.message.reply_text("❌ מספר רכב חייב להיות 8 ספרות בדיוק!\nנסה שוב:")
        return
    
    # Format car number: 12345678 -> 123-45-678
    formatted_number = f"{car_number[:3]}-{car_number[3:5]}-{car_number[5:]}"
    context.user_data["car_number"] = formatted_number
    context.user_data["state"] = "waiting_pickup"
    
    await update.message.reply_text(f"מספר רכב: {formatted_number} ✅\n\nהזן מיקום איסוף:")

async def handle_pickup_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pickup location input"""
    context.user_data["pickup"] = update.message.text.strip()
    context.user_data["state"] = "waiting_dropoff"
    
    await update.message.reply_text("מיקום איסוף נשמר ✅\n\nהזן מיקום הורדה:")

async def handle_dropoff_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle dropoff location input"""
    context.user_data["dropoff"] = update.message.text.strip()
    context.user_data["state"] = "waiting_notes"
    
    await update.message.reply_text("מיקום הורדה נשמר ✅\n\nהזן הערות (או כתב 'ללא'):")

async def handle_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle notes input and show job type buttons"""
    notes = update.message.text.strip()
    context.user_data["notes"] = notes if notes.lower() != "ללא" else ""
    
    keyboard = [
        [InlineKeyboardButton("🚚 משימת שינוע", callback_data="job_type_שינוע")],
        [InlineKeyboardButton("🔄 משימת סרק", callback_data="job_type_סרק")],
        [InlineKeyboardButton("🚗 משימת טרמפ", callback_data="job_type_טרמפ")],
        [InlineKeyboardButton("🔧 משימת מוסך", callback_data="job_type_מוסך")],
        [InlineKeyboardButton("🧪 משימת טסט", callback_data="job_type_טסט")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("הערות נשמרו ✅\n\nבחר סוג משימה:", reply_markup=reply_markup)

async def handle_job_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle job type selection and save job"""
    job_type = update.callback_query.data.replace("job_type_", "")
    
    # Create job record
    job = {
        "car_number": context.user_data["car_number"],
        "pickup": context.user_data["pickup"],
        "dropoff": context.user_data["dropoff"],
        "notes": context.user_data["notes"],
        "job_type": job_type,
        "time": datetime.now(IST).strftime("%H:%M")
    }
    
    # Save to daily jobs
    today = bot_instance.get_today_key()
    if today not in bot_instance.data["daily_jobs"]:
        bot_instance.data["daily_jobs"][today] = []
    
    bot_instance.data["daily_jobs"][today].append(job)
    
    # Update monthly stats
    month = bot_instance.get_month_key()
    if month not in bot_instance.data["monthly_stats"]:
        bot_instance.data["monthly_stats"][month] = {}
    
    if job_type not in bot_instance.data["monthly_stats"][month]:
        bot_instance.data["monthly_stats"][month][job_type] = 0
    
    bot_instance.data["monthly_stats"][month][job_type] += 1
    
    bot_instance.save_data()
    
    # Clear user data
    context.user_data.clear()
    
    await update.callback_query.edit_message_text(
        f"✅ המשימה נשמרה בהצלחה!\n\n"
        f"🚗 רכב: {job['car_number']}\n"
        f"📍 מ: {job['pickup']}\n"
        f"📍 ל: {job['dropoff']}\n"
        f"📝 הערות: {job['notes'] or 'ללא'}\n"
        f"🏷️ סוג: משימת {job_type}\n"
        f"🕐 שעה: {job['time']}"
    )
    
    await start(update, context)

async def end_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show end of day summary"""
    today = bot_instance.get_today_key()
    today_jobs = bot_instance.data["daily_jobs"].get(today, [])
    
    if not today_jobs:
        await update.callback_query.edit_message_text("אין משימות להיום! 📝")
        await start(update, context)
        return
    
    # Count job types
    job_counts = {}
    for job in today_jobs:
        job_type = job["job_type"]
        job_counts[job_type] = job_counts.get(job_type, 0) + 1
    
    # Create summary
    summary = f"📊 סיכום יום {today}\n\n"
    summary += f"📈 סה\"ך משימות: {len(today_jobs)}\n\n"
    
    for job_type, count in job_counts.items():
        summary += f"• משימת {job_type}: {count}\n"
    
    # Monthly stats
    month = bot_instance.get_month_key()
    monthly_stats = bot_instance.data["monthly_stats"].get(month, {})
    if monthly_stats:
        summary += f"\n📅 סיכום חודשי ({month}):\n"
        total_monthly = sum(monthly_stats.values())
        summary += f"סה\"ך: {total_monthly}\n"
        for job_type, count in monthly_stats.items():
            summary += f"• {job_type}: {count}\n"
    
    keyboard = [
        [InlineKeyboardButton("📧 שלח מייל", callback_data="send_email_yes")],
        [InlineKeyboardButton("🚫 דלג", callback_data="send_email_no")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(summary, reply_markup=reply_markup)

async def send_daily_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send daily summary email"""
    today = bot_instance.get_today_key()
    today_jobs = bot_instance.data["daily_jobs"].get(today, [])
    
    # Create email content
    subject = f"דוח יומי - {today}"
    
    body = f"דוח עבודה יומי - {today}\n\n"
    body += f"סה\"ך משימות: {len(today_jobs)}\n\n"
    
    job_counts = {}
    for i, job in enumerate(today_jobs, 1):
        job_type = job["job_type"]
        job_counts[job_type] = job_counts.get(job_type, 0) + 1
        
        body += f"{i}. רכב {job['car_number']} - {job['time']}\n"
        body += f"   מ: {job['pickup']}\n"
        body += f"   ל: {job['dropoff']}\n"
        body += f"   סוג: משימת {job_type}\n"
        if job['notes']:
            body += f"   הערות: {job['notes']}\n"
        body += "\n"
    
    body += "סיכום לפי סוג משימה:\n"
    for job_type, count in job_counts.items():
        body += f"• משימת {job_type}: {count}\n"
    
    try:
        # Send email
        msg = MIMEMultipart()
        msg['From'] = EMAIL
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL, EMAIL_PASSWORD)
        
        for email_addr in bot_instance.data["emails"]:
            msg['To'] = email_addr
            server.send_message(msg)
            del msg['To']
        
        server.quit()
        
        # Clear today's data after successful email
        if today in bot_instance.data["daily_jobs"]:
            del bot_instance.data["daily_jobs"][today]
        bot_instance.save_data()
        
        await update.callback_query.edit_message_text(
            f"✅ המייל נשלח בהצלחה ל-{len(bot_instance.data['emails'])} כתובות!\n"
            "נתוני היום נמחקו."
        )
        
    except Exception as e:
        await update.callback_query.edit_message_text(f"❌ שגיאה בשליחת מייל: {str(e)}")
    
    await start(update, context)

async def edit_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show today's jobs for editing/deleting"""
    today = bot_instance.get_today_key()
    today_jobs = bot_instance.data["daily_jobs"].get(today, [])
    
    if not today_jobs:
        await update.callback_query.edit_message_text("אין משימות להיום לעריכה! 📝")
        await start(update, context)
        return
    
    keyboard = []
    for i, job in enumerate(today_jobs):
        job_text = f"{job['car_number']} - {job['job_type']} ({job['time']})"
        keyboard.append([
            InlineKeyboardButton(f"✏️ {job_text}", callback_data=f"edit_job_{i}"),
            InlineKeyboardButton("🗑️", callback_data=f"delete_job_{i}")
        ])
    
    keyboard.append([InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back_main")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "בחר משימה לעריכה או מחיקה:",
        reply_markup=reply_markup
    )

async def handle_edit_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle job editing (simplified - just show job details)"""
    job_index = int(update.callback_query.data.replace("edit_job_", ""))
    today = bot_instance.get_today_key()
    today_jobs = bot_instance.data["daily_jobs"].get(today, [])
    
    if job_index < len(today_jobs):
        job = today_jobs[job_index]
        details = (
            f"📋 פרטי משימה #{job_index + 1}:\n\n"
            f"🚗 רכב: {job['car_number']}\n"
            f"📍 מ: {job['pickup']}\n"
            f"📍 ל: {job['dropoff']}\n"
            f"📝 הערות: {job['notes'] or 'ללא'}\n"
            f"🏷️ סוג: משימת {job['job_type']}\n"
            f"🕐 שעה: {job['time']}\n\n"
            "עריכה מתקדמת תתווסף בגרסה הבאה."
        )
        
        keyboard = [
            [InlineKeyboardButton("🗑️ מחק משימה", callback_data=f"delete_job_{job_index}")],
            [InlineKeyboardButton("🔙 חזור", callback_data="edit_delete")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(details, reply_markup=reply_markup)

async def handle_delete_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle job deletion"""
    job_index = int(update.callback_query.data.replace("delete_job_", ""))
    today = bot_instance.get_today_key()
    today_jobs = bot_instance.data["daily_jobs"].get(today, [])
    
    if job_index < len(today_jobs):
        deleted_job = today_jobs.pop(job_index)
        
        # Update monthly stats
        month = bot_instance.get_month_key()
        if month in bot_instance.data["monthly_stats"]:
            job_type = deleted_job["job_type"]
            if job_type in bot_instance.data["monthly_stats"][month]:
                bot_instance.data["monthly_stats"][month][job_type] -= 1
                if bot_instance.data["monthly_stats"][month][job_type] <= 0:
                    del bot_instance.data["monthly_stats"][month][job_type]
        
        bot_instance.save_data()
        
        await update.callback_query.edit_message_text(
            f"✅ המשימה נמחקה:\n{deleted_job['car_number']} - משימת {deleted_job['job_type']}"
        )
        await edit_delete(update, context)

async def manage_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage email addresses"""
    emails_list = "\n".join([f"• {email}" for email in bot_instance.data["emails"]])
    
    keyboard = [
        [InlineKeyboardButton("➕ הוסף מייל", callback_data="add_email")],
        [InlineKeyboardButton("🗑️ מחק מייל", callback_data="delete_email")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        f"📧 ניהול כתובות מייל:\n\n{emails_list}",
        reply_markup=reply_markup
    )

async def handle_email_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email-related actions"""
    action = update.callback_query.data
    
    if action == "add_email":
        context.user_data["state"] = "waiting_email"
        await update.callback_query.edit_message_text("הזן כתובת מייל חדשה:")
    elif action == "delete_email":
        if len(bot_instance.data["emails"]) <= 1:
            await update.callback_query.edit_message_text("לא ניתן למחוק - חייבת להיות לפחות כתובת אחת!")
            await manage_emails(update, context)
            return
        
        keyboard = []
        for i, email in enumerate(bot_instance.data["emails"]):
            keyboard.append([InlineKeyboardButton(f"🗑️ {email}", callback_data=f"del_email_{i}")])
        keyboard.append([InlineKeyboardButton("🔙 חזור", callback_data="manage_emails")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text("בחר מייל למחיקה:", reply_markup=reply_markup)
    elif action.startswith("del_email_"):
        email_index = int(action.replace("del_email_", ""))
        if email_index < len(bot_instance.data["emails"]):
            deleted_email = bot_instance.data["emails"].pop(email_index)
            bot_instance.save_data()
            await update.callback_query.edit_message_text(f"✅ המייל נמחק: {deleted_email}")
            await manage_emails(update, context)

async def handle_new_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle new email address input"""
    email = update.message.text.strip()
    
    if "@" not in email or "." not in email:
        await update.message.reply_text("❌ כתובת מייל לא תקינה! נסה שוב:")
        return
    
    if email not in bot_instance.data["emails"]:
        bot_instance.data["emails"].append(email)
        bot_instance.save_data()
        await update.message.reply_text(f"✅ המייל נוסף: {email}")
    else:
        await update.message.reply_text("המייל כבר קיים ברשימה!")
    
    context.user_data.clear()
    await start(update, context)

def main():
    """Main function to run the bot"""
    # Clean old data on startup
    bot_instance.cleanup_old_data()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start the bot
    print("Bot starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
