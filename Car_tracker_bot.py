import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import json
from datetime import datetime, timedelta
from collections import defaultdict

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
START, CAR_NUMBER, PICKUP, DROPOFF, NOTE, NEXT_OR_END = range(6)

# Data storage (in production, use a proper database)
user_data = {}
monthly_stats = defaultdict(int)

def load_data():
    """Load user data from file"""
    global user_data, monthly_stats
    try:
        if os.path.exists('user_data.json'):
            with open('user_data.json', 'r') as f:
                data = json.load(f)
                user_data = data.get('user_data', {})
                monthly_stats = defaultdict(int, data.get('monthly_stats', {}))
        else:
            user_data = {}
            monthly_stats = defaultdict(int)
    except Exception as e:
        logger.error(f"Error loading data: {e}")
        user_data = {}
        monthly_stats = defaultdict(int)

def save_data():
    """Save user data to file"""
    try:
        data = {
            'user_data': user_data,
            'monthly_stats': dict(monthly_stats)
        }
        with open('user_data.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving data: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the car tracking session"""
    user_id = str(update.effective_user.id)
    
    # Initialize user data if not exists
    if user_id not in user_data:
        user_data[user_id] = {
            'daily_cars': [],
            'current_car': {}
        }
    
    # Clear current car data for new session
    user_data[user_id]['current_car'] = {}
    
    await update.message.reply_text(
        "🚗 Car Tracking Started!\n\n"
        "Please enter the car number:"
    )
    
    return CAR_NUMBER

async def get_car_number(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get car number from user"""
    user_id = str(update.effective_user.id)
    car_number = update.message.text.strip()
    
    user_data[user_id]['current_car']['car_number'] = car_number
    user_data[user_id]['current_car']['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    await update.message.reply_text(
        f"🚗 Car Number: {car_number}\n\n"
        "Please enter the pickup location:"
    )
    
    return PICKUP

async def get_pickup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get pickup location from user"""
    user_id = str(update.effective_user.id)
    pickup = update.message.text.strip()
    
    user_data[user_id]['current_car']['pickup'] = pickup
    
    await update.message.reply_text(
        f"📍 Pickup: {pickup}\n\n"
        "Please enter the drop-off location:"
    )
    
    return DROPOFF

async def get_dropoff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Get drop-off location from user"""
    user_id = str(update.effective_user.id)
    dropoff = update.message.text.strip()
    
    user_data[user_id]['current_car']['dropoff'] = dropoff
    
    reply_keyboard = [['Skip Note', 'Add Note']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"📍 Drop-off: {dropoff}\n\n"
        "Would you like to add a note for this trip?",
        reply_markup=markup
    )
    
    return NOTE

async def handle_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle note input or skip"""
    user_id = str(update.effective_user.id)
    text = update.message.text.strip()
    
    if text == "Skip Note":
        user_data[user_id]['current_car']['note'] = ""
    elif text == "Add Note":
        await update.message.reply_text(
            "📝 Please enter your note:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NOTE  # Stay in NOTE state to get the actual note
    else:
        # This is the actual note
        user_data[user_id]['current_car']['note'] = text
    
    # Add current car to daily list
    user_data[user_id]['daily_cars'].append(user_data[user_id]['current_car'].copy())
    
    # Update monthly stats
    current_month = datetime.now().strftime("%Y-%m")
    monthly_stats[f"{user_id}_{current_month}"] += 1
    
    save_data()
    
    reply_keyboard = [['Next Car', 'End Day']]
    markup = ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    car_info = user_data[user_id]['current_car']
    await update.message.reply_text(
        f"✅ Car recorded!\n\n"
        f"🚗 {car_info['car_number']}\n"
        f"📍 From: {car_info['pickup']}\n"
        f"📍 To: {car_info['dropoff']}\n"
        f"📝 Note: {car_info['note'] if car_info['note'] else 'None'}\n"
        f"⏰ Time: {car_info['timestamp']}\n\n"
        "What would you like to do next?",
        reply_markup=markup
    )
    
    return NEXT_OR_END

async def handle_next_or_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle next car or end day choice"""
    user_id = str(update.effective_user.id)
    choice = update.message.text.strip()
    
    if choice == "Next Car":
        user_data[user_id]['current_car'] = {}
        await update.message.reply_text(
            "🚗 Next car ready!\n\n"
            "Please enter the car number:",
            reply_markup=ReplyKeyboardRemove()
        )
        return CAR_NUMBER
    
    elif choice == "End Day":
        return await end_day(update, context)
    
    return NEXT_OR_END

async def end_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End the day and show summary"""
    user_id = str(update.effective_user.id)
    daily_cars = user_data[user_id]['daily_cars']
    
    if not daily_cars:
        await update.message.reply_text(
            "📊 No cars recorded today!\n\n"
            "Use /start to begin tracking.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Generate summary for display
    summary = f"📊 **DAILY SUMMARY - {datetime.now().strftime('%Y-%m-%d')}**\n\n"
    summary += f"🚗 Total Cars: {len(daily_cars)}\n\n"
    
    for i, car in enumerate(daily_cars, 1):
        summary += f"**Car #{i}**\n"
        summary += f"🚗 Number: {car['car_number']}\n"
        summary += f"📍 From: {car['pickup']}\n"
        summary += f"📍 To: {car['dropoff']}\n"
        if car['note']:
            summary += f"📝 Note: {car['note']}\n"
        summary += f"⏰ Time: {car['timestamp']}\n"
        summary += "─" * 30 + "\n\n"
    
    # Monthly stats
    current_month = datetime.now().strftime("%Y-%m")
    monthly_total = monthly_stats[f"{user_id}_{current_month}"]
    summary += f"📅 **This Month Total: {monthly_total} missions**\n\n"
    summary += "Screenshot this summary! 📸"
    
    # Generate plain text copy version
    copy_text = f"DAILY SUMMARY - {datetime.now().strftime('%Y-%m-%d')}\n\n"
    copy_text += f"Total Cars: {len(daily_cars)}\n\n"
    
    for i, car in enumerate(daily_cars, 1):
        copy_text += f"Car #{i}\n"
        copy_text += f"Number: {car['car_number']}\n"
        copy_text += f"From: {car['pickup']}\n"
        copy_text += f"To: {car['dropoff']}\n"
        if car['note']:
            copy_text += f"Note: {car['note']}\n"
        copy_text += f"Time: {car['timestamp']}\n"
        copy_text += "------------------------------\n\n"
    
    copy_text += f"This Month Total: {monthly_total} missions"
    
    await update.message.reply_text(
        summary,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )
    
    # Send copyable version
    await update.message.reply_text(
        f"📋 **COPY VERSION:**\n\n`{copy_text}`",
        parse_mode='Markdown'
    )
    
    # Clear daily data for next day
    user_data[user_id]['daily_cars'] = []
    save_data()
    
    await update.message.reply_text(
        "Day ended! Use /start to begin a new tracking session.\n"
        "Use /stats to see your monthly statistics.\n\n"
        "💡 Tip: Tap and hold the copy version above to easily copy the text!"
    )
    
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show monthly statistics"""
    user_id = str(update.effective_user.id)
    current_month = datetime.now().strftime("%Y-%m")
    
    stats_text = f"📊 **MONTHLY STATISTICS**\n\n"
    stats_text += f"📅 Current Month ({current_month}):\n"
    stats_text += f"🚗 Total Missions: {monthly_stats[f'{user_id}_{current_month}']}\n\n"
    
    # Show last 3 months
    for i in range(1, 4):
        past_date = datetime.now() - timedelta(days=30*i)
        past_month = past_date.strftime("%Y-%m")
        past_total = monthly_stats[f"{user_id}_{past_month}"]
        if past_total > 0:
            stats_text += f"📅 {past_month}: {past_total} missions\n"
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation"""
    await update.message.reply_text(
        "🚫 Car tracking cancelled. Use /start to begin again.",
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
    
    # Add conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CAR_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_car_number)],
            PICKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pickup)],
            DROPOFF: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dropoff)],
            NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_note)],
            NEXT_OR_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_next_or_end)],
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
