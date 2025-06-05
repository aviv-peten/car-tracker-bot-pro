import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Dict, List
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8195716721:AAGfrro7LCy1WTr4QccCZgtnIJvt3M6CdVI"
EMAIL_ADDRESS = "Avivpeten123456789@gmail.com"
EMAIL_PASSWORD = "ycqx xqaf xicz ywgi"

class CarTrackerBot:
    def __init__(self):
        self.user_data = {}
        self.daily_jobs = {}
        self.monthly_stats = {}
        self.email_list = []
        self.load_data()

    def load_data(self):
        """Load data from files if they exist"""
        try:
            if os.path.exists('monthly_stats.json'):
                with open('monthly_stats.json', 'r', encoding='utf-8') as f:
                    self.monthly_stats = json.load(f)
            if os.path.exists('email_list.json'):
                with open('email_list.json', 'r', encoding='utf-8') as f:
                    self.email_list = json.load(f)
        except Exception as e:
            logger.error(f"Error loading data: {e}")

    def save_data(self):
        """Save data to files"""
        try:
            with open('monthly_stats.json', 'w', encoding='utf-8') as f:
                json.dump(self.monthly_stats, f, ensure_ascii=False, indent=2)
            with open('email_list.json', 'w', encoding='utf-8') as f:
                json.dump(self.email_list, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")

    def format_car_number(self, number: str) -> str:
        """Format car number from 11111111 to 111-11-111"""
        if len(number) == 8 and number.isdigit():
            return f"{number[:3]}-{number[3:5]}-{number[5:]}"
        return number

    def get_main_menu_keyboard(self):
        """Get main menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("רכב חדש", callback_data="new_car")],
            [InlineKeyboardButton("סוף יום", callback_data="end_day")],
            [InlineKeyboardButton("עריכה/מחיקה", callback_data="edit_delete")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_job_type_keyboard(self):
        """Get job type selection keyboard"""
        keyboard = [
            [InlineKeyboardButton("משימת שינוע", callback_data="job_שינוע")],
            [InlineKeyboardButton("משימת סרק", callback_data="job_סרק")],
            [InlineKeyboardButton("משימת טרמפ", callback_data="job_טרמפ")],
            [InlineKeyboardButton("משימת מוסך", callback_data="job_מוסך")],
            [InlineKeyboardButton("משימת טסט", callback_data="job_טסט")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_number_keyboard(self):
        """Get number input keyboard"""
        keyboard = []
        for i in range(0, 10, 3):
            row = []
            for j in range(3):
                if i + j < 10:
                    row.append(KeyboardButton(str(i + j)))
            keyboard.append(row)
        keyboard.append([KeyboardButton("מחק"), KeyboardButton("אישור")])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_yes_no_keyboard(self):
        """Get yes/no keyboard"""
        keyboard = [
            [InlineKeyboardButton("כן", callback_data="yes")],
            [InlineKeyboardButton("דלג", callback_data="skip")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start command handler"""
        user_id = update.effective_user.id
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id not in self.daily_jobs:
            self.daily_jobs[user_id] = {}
        if today not in self.daily_jobs[user_id]:
            self.daily_jobs[user_id][today] = []

        await update.message.reply_text(
            "ברוכים הבאים למעקב רכבים!\nבחר פעולה:",
            reply_markup=self.get_main_menu_keyboard()
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        data = query.data

        if data == "new_car":
            await self.start_new_car(query, context)
        elif data == "end_day":
            await self.end_of_day(query, context)
        elif data == "edit_delete":
            await self.edit_delete_menu(query, context)
        elif data.startswith("job_"):
            job_type = data.replace("job_", "")
            await self.save_job(query, context, job_type)
        elif data == "yes":
            await self.show_email_list(query, context)
        elif data == "skip":
            await self.finish_end_of_day(query, context)
        elif data.startswith("email_"):
            await self.toggle_email(query, context, data)
        elif data == "send_emails":
            await self.send_daily_report(query, context)
        elif data.startswith("delete_"):
            await self.delete_job(query, context, data)

    async def start_new_car(self, query, context):
        """Start new car entry process"""
        user_id = query.from_user.id
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        
        self.user_data[user_id]['state'] = 'entering_car_number'
        self.user_data[user_id]['car_number_input'] = ''
        
        await query.edit_message_text(
            "הכנס מספר רכב (8 ספרות):\nמספר נוכחי: ",
            reply_markup=None
        )
        
        # Send number keyboard
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="השתמש במקלדת למטה:",
            reply_markup=self.get_number_keyboard()
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        user_id = update.effective_user.id
        text = update.message.text
        
        if user_id not in self.user_data:
            self.user_data[user_id] = {}

        state = self.user_data[user_id].get('state', '')

        if state == 'entering_car_number':
            await self.handle_car_number_input(update, context, text)
        elif state == 'entering_pickup':
            await self.handle_pickup_input(update, context, text)
        elif state == 'entering_dropoff':
            await self.handle_dropoff_input(update, context, text)
        elif state == 'entering_note':
            await self.handle_note_input(update, context, text)
        elif state == 'adding_email':
            await self.handle_email_input(update, context, text)

    async def handle_car_number_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle car number input"""
        user_id = update.effective_user.id
        
        if text == "מחק":
            self.user_data[user_id]['car_number_input'] = ''
            await update.message.reply_text("מספר נוכחי: ")
        elif text == "אישור":
            car_number = self.user_data[user_id]['car_number_input']
            if len(car_number) == 8:
                formatted_number = self.format_car_number(car_number)
                self.user_data[user_id]['car_number'] = formatted_number
                self.user_data[user_id]['state'] = 'entering_pickup'
                await update.message.reply_text(
                    f"מספר רכב: {formatted_number}\n\nהכנס מקום איסוף:",
                    reply_markup=None
                )
            else:
                await update.message.reply_text("מספר רכב חייב להיות 8 ספרות")
        elif text.isdigit() and len(text) == 1:
            current = self.user_data[user_id]['car_number_input']
            if len(current) < 8:
                self.user_data[user_id]['car_number_input'] += text
                await update.message.reply_text(f"מספר נוכחי: {self.user_data[user_id]['car_number_input']}")

    async def handle_pickup_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle pickup location input"""
        user_id = update.effective_user.id
        self.user_data[user_id]['pickup'] = text
        self.user_data[user_id]['state'] = 'entering_dropoff'
        await update.message.reply_text("הכנס מקום הורדה:")

    async def handle_dropoff_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle dropoff location input"""
        user_id = update.effective_user.id
        self.user_data[user_id]['dropoff'] = text
        self.user_data[user_id]['state'] = 'entering_note'
        await update.message.reply_text("הכנס הערה:")

    async def handle_note_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle note input"""
        user_id = update.effective_user.id
        self.user_data[user_id]['note'] = text
        self.user_data[user_id]['state'] = 'selecting_job_type'
        
        await update.message.reply_text(
            "בחר סוג משימה:",
            reply_markup=self.get_job_type_keyboard()
        )

    async def save_job(self, query, context, job_type):
        """Save the job"""
        user_id = query.from_user.id
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id not in self.daily_jobs:
            self.daily_jobs[user_id] = {}
        if today not in self.daily_jobs[user_id]:
            self.daily_jobs[user_id][today] = []

        job = {
            'car_number': self.user_data[user_id]['car_number'],
            'pickup': self.user_data[user_id]['pickup'],
            'dropoff': self.user_data[user_id]['dropoff'],
            'note': self.user_data[user_id]['note'],
            'job_type': job_type,
            'time': datetime.now().strftime('%H:%M')
        }
        
        self.daily_jobs[user_id][today].append(job)
        self.user_data[user_id]['state'] = ''
        
        await query.edit_message_text(
            f"משימה נשמרה בהצלחה!\n"
            f"רכב: {job['car_number']}\n"
            f"איסוף: {job['pickup']}\n"
            f"הורדה: {job['dropoff']}\n"
            f"הערה: {job['note']}\n"
            f"סוג: {job['job_type']}\n"
            f"שעה: {job['time']}\n\n"
            f"בחר פעולה:",
            reply_markup=self.get_main_menu_keyboard()
        )

    async def end_of_day(self, query, context):
        """Handle end of day"""
        user_id = query.from_user.id
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id not in self.daily_jobs or today not in self.daily_jobs[user_id]:
            await query.edit_message_text(
                "אין משימות להיום.\n\nבחר פעולה:",
                reply_markup=self.get_main_menu_keyboard()
            )
            return

        jobs = self.daily_jobs[user_id][today]
        total_jobs = len(jobs)
        
        # Count job types
        job_counts = {}
        for job in jobs:
            job_type = job['job_type']
            job_counts[job_type] = job_counts.get(job_type, 0) + 1

        # Update monthly stats
        month = datetime.now().strftime('%Y-%m')
        if user_id not in self.monthly_stats:
            self.monthly_stats[user_id] = {}
        if month not in self.monthly_stats[user_id]:
            self.monthly_stats[user_id][month] = {}
        
        for job_type, count in job_counts.items():
            if job_type not in self.monthly_stats[user_id][month]:
                self.monthly_stats[user_id][month][job_type] = 0
            self.monthly_stats[user_id][month][job_type] += count

        # Generate report
        report = f"דוח סוף יום - {today}\n\n"
        report += f"סך הכל משימות: {total_jobs}\n\n"
        
        for job_type, count in job_counts.items():
            report += f"{job_type}: {count}\n"
        
        report += "\nסטטיסטיקה חודשית:\n"
        for i in range(3):
            month_date = datetime.now() - timedelta(days=30*i)
            month_key = month_date.strftime('%Y-%m')
            if month_key in self.monthly_stats.get(user_id, {}):
                report += f"\n{month_date.strftime('%m/%Y')}:\n"
                month_data = self.monthly_stats[user_id][month_key]
                for job_type, count in month_data.items():
                    report += f"  {job_type}: {count}\n"

        self.save_data()
        
        await query.edit_message_text(
            report + "\n\nרוצה לשלוח דוח במייל?",
            reply_markup=self.get_yes_no_keyboard()
        )

    async def show_email_list(self, query, context):
        """Show email list for selection"""
        keyboard = []
        for email in self.email_list:
            keyboard.append([InlineKeyboardButton(f"✓ {email}", callback_data=f"email_{email}")])
        
        keyboard.append([InlineKeyboardButton("הוסף מייל חדש", callback_data="add_email")])
        keyboard.append([InlineKeyboardButton("שלח דוח", callback_data="send_emails")])
        keyboard.append([InlineKeyboardButton("דלג", callback_data="skip")])
        
        await query.edit_message_text(
            "בחר מיילים לשליחה:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def toggle_email(self, query, context, data):
        """Toggle email selection"""
        email = data.replace("email_", "")
        user_id = query.from_user.id
        
        if user_id not in self.user_data:
            self.user_data[user_id] = {}
        if 'selected_emails' not in self.user_data[user_id]:
            self.user_data[user_id]['selected_emails'] = []
        
        if email in self.user_data[user_id]['selected_emails']:
            self.user_data[user_id]['selected_emails'].remove(email)
        else:
            self.user_data[user_id]['selected_emails'].append(email)
        
        # Refresh the keyboard
        keyboard = []
        for e in self.email_list:
            prefix = "✓" if e in self.user_data[user_id]['selected_emails'] else "○"
            keyboard.append([InlineKeyboardButton(f"{prefix} {e}", callback_data=f"email_{e}")])
        
        keyboard.append([InlineKeyboardButton("הוסף מייל חדש", callback_data="add_email")])
        keyboard.append([InlineKeyboardButton("שלח דוח", callback_data="send_emails")])
        keyboard.append([InlineKeyboardButton("דלג", callback_data="skip")])
        
        await query.edit_message_text(
            "בחר מיילים לשליחה:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def send_daily_report(self, query, context):
        """Send daily report via email"""
        user_id = query.from_user.id
        today = datetime.now().strftime('%Y-%m-%d')
        
        selected_emails = self.user_data[user_id].get('selected_emails', [])
        if not selected_emails:
            await query.edit_message_text("לא נבחרו מיילים.")
            return

        # Generate email content
        jobs = self.daily_jobs[user_id][today]
        
        email_content = f"דוח יומי - {today}\n\n"
        email_content += f"סך הכל משימות: {len(jobs)}\n\n"
        
        for i, job in enumerate(jobs, 1):
            email_content += f"משימה {i}:\n"
            email_content += f"  רכב: {job['car_number']}\n"
            email_content += f"  איסוף: {job['pickup']}\n"
            email_content += f"  הורדה: {job['dropoff']}\n"
            email_content += f"  הערה: {job['note']}\n"
            email_content += f"  סוג: {job['job_type']}\n"
            email_content += f"  שעה: {job['time']}\n\n"

        # Send emails
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            
            for email in selected_emails:
                msg = MIMEMultipart()
                msg['From'] = EMAIL_ADDRESS
                msg['To'] = email
                msg['Subject'] = f"דוח יומי - {today}"
                
                msg.attach(MIMEText(email_content, 'plain', 'utf-8'))
                
                server.send_message(msg)
            
            server.quit()
            
            await query.edit_message_text(
                f"דוח נשלח בהצלחה ל-{len(selected_emails)} מיילים!",
                reply_markup=self.get_main_menu_keyboard()
            )
            
        except Exception as e:
            await query.edit_message_text(f"שגיאה בשליחת מייל: {str(e)}")
        
        await self.finish_end_of_day(query, context)

    async def finish_end_of_day(self, query, context):
        """Finish end of day process"""
        user_id = query.from_user.id
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Clear today's jobs
        if user_id in self.daily_jobs and today in self.daily_jobs[user_id]:
            del self.daily_jobs[user_id][today]
        
        # Clear user state
        if user_id in self.user_data:
            self.user_data[user_id] = {}
        
        await query.edit_message_text(
            "סוף יום הושלם בהצלחה!\n\nבחר פעולה:",
            reply_markup=self.get_main_menu_keyboard()
        )

    async def edit_delete_menu(self, query, context):
        """Show edit/delete menu"""
        user_id = query.from_user.id
        today = datetime.now().strftime('%Y-%m-%d')
        
        if user_id not in self.daily_jobs or today not in self.daily_jobs[user_id]:
            await query.edit_message_text(
                "אין משימות להיום.\n\nבחר פעולה:",
                reply_markup=self.get_main_menu_keyboard()
            )
            return

        jobs = self.daily_jobs[user_id][today]
        keyboard = []
        
        for i, job in enumerate(jobs):
            text = f"{job['car_number']} - {job['pickup']} → {job['dropoff']}"
            keyboard.append([InlineKeyboardButton(f"מחק: {text}", callback_data=f"delete_{i}")])
        
        keyboard.append([InlineKeyboardButton("חזור לתפריט הראשי", callback_data="main_menu")])
        
        await query.edit_message_text(
            "בחר משימה למחיקה:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def delete_job(self, query, context, data):
        """Delete a job"""
        user_id = query.from_user.id
        today = datetime.now().strftime('%Y-%m-%d')
        job_index = int(data.replace("delete_", ""))
        
        if user_id in self.daily_jobs and today in self.daily_jobs[user_id]:
            if 0 <= job_index < len(self.daily_jobs[user_id][today]):
                deleted_job = self.daily_jobs[user_id][today].pop(job_index)
                await query.edit_message_text(
                    f"משימה נמחקה: {deleted_job['car_number']}\n\nבחר פעולה:",
                    reply_markup=self.get_main_menu_keyboard()
                )
            else:
                await query.edit_message_text(
                    "שגיאה במחיקת המשימה.\n\nבחר פעולה:",
                    reply_markup=self.get_main_menu_keyboard()
                )

    async def handle_email_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Handle email input"""
        if "@" in text and "." in text:
            if text not in self.email_list:
                self.email_list.append(text)
                self.save_data()
                await update.message.reply_text(f"מייל נוסף: {text}")
            else:
                await update.message.reply_text("מייל כבר קיים ברשימה")
        else:
            await update.message.reply_text("מייל לא תקין")

def main():
    """Main function"""
    bot = CarTrackerBot()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot.start))
    application.add_handler(CallbackQueryHandler(bot.button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
