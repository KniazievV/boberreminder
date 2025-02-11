from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import datetime
from flask import Flask
from threading import Thread

# Словарь для хранения этапов пользователя
user_stage = {}

# Словарь для хранения напоминаний (каждый пользователь имеет список напоминаний)
reminders = {}

# Клавиатура с кнопками
def main_menu_keyboard():
    return ReplyKeyboardMarkup([['Добавить', 'Список', 'Инфо']], resize_keyboard=True)

# Функция для запуска бота
async def start(update: Update, context):
    user_id = update.message.from_user.id
    # Если у пользователя нет напоминаний, создаем пустой список
    if user_id not in reminders:
        reminders[user_id] = []

    user_stage[user_id] = 'reminder_text'
    await update.message.reply_text("О чём нужно напомнить?", reply_markup=main_menu_keyboard())

# Функция для обработки нажатия на кнопку "Инфо"
async def show_info(update: Update, context):
    info_message = (
        "Это бот для напоминаний\n\n"
        "Формат даты - dd.mm.yyyy\n"
        "Формат времени - hh:mm\n\n"
        "Сделано [Бобром](https://t.me/beboberbro)\n\n"
        "Планируется:\n"
        "- Очистка истории\n"
    )
    await update.message.reply_text(info_message, parse_mode="Markdown", disable_web_page_preview=True)

# Обработчик текстовых сообщений
async def handle_message(update: Update, context):
    user_id = update.message.from_user.id
    message_text = update.message.text

    if message_text == 'Добавить':
        await start(update, context)
    elif message_text == 'Список':
        await show_reminders(update, context)
    elif message_text == 'Инфо':
        await show_info(update, context)
    elif user_stage.get(user_id) == 'reminder_text':
        reminders[user_id].append({'text': message_text, 'date': '', 'time': ''})
        user_stage[user_id] = 'reminder_date'
        await update.message.reply_text("Когда нужно напомнить?", reply_markup=InlineKeyboardMarkup([[ 
            InlineKeyboardButton("Сегодня", callback_data='today'), 
            InlineKeyboardButton("Завтра", callback_data='tomorrow') 
        ]]))
    elif user_stage.get(user_id) == 'reminder_date':
        try:
            datetime.datetime.strptime(message_text, '%d.%m.%Y')
            reminders[user_id][-1]['date'] = message_text
            user_stage[user_id] = 'reminder_time'
            await update.message.reply_text("Во сколько нужно напомнить?", reply_markup=InlineKeyboardMarkup([[ 
                InlineKeyboardButton("+1 мин", callback_data='plus_one'),
                InlineKeyboardButton("+5 мин", callback_data='plus_five') 
            ]]))
        except ValueError:
            await update.message.reply_text("Неверный формат даты! Пожалуйста, введи дату в формате DD.MM.YYYY")
    elif user_stage.get(user_id) == 'reminder_time':
        await update.message.reply_text("Пожалуйста, введи время в формате HH:MM")

# Обработчик команды /list
async def show_reminders(update: Update, context):
    user_id = update.message.from_user.id
    current_time = datetime.datetime.now()

    if reminders.get(user_id):
        active_reminders = []
        for r in reminders[user_id]:
            if r['date'] and r['time']:  # Проверка, чтобы дата и время были заполнены
                try:
                    reminder_time = datetime.datetime.strptime(f"{r['date']} {r['time']}", '%d.%m.%Y %H:%M')
                    if reminder_time > current_time:
                        active_reminders.append(r)
                except ValueError:
                    continue

        reminders[user_id] = active_reminders

        if active_reminders:
            reminder_list = "\n".join(
                [f"Напоминание {i+1}: **{r['text']}** на {r['date']} в {r['time']}" for i, r in enumerate(active_reminders)]
            )
            await update.message.reply_text(reminder_list, parse_mode="Markdown")
        else:
            await update.message.reply_text("У тебя нет актуальных напоминаний")
    else:
        await update.message.reply_text("У тебя нет напоминаний")

# Функция для отправки уведомлений
async def send_reminder(context):
    job = context.job
    await context.bot.send_message(
        chat_id=job.data['chat_id'],
        text=f"Напоминание: **{job.data['text']}** на {job.data['date']} в {job.data['time']}",
        parse_mode="Markdown"
    )

# Обработчик нажатий на кнопки
async def handle_callback(update: Update, context):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if query.data == 'today':
        reminders[user_id][-1]['date'] = datetime.datetime.now().strftime('%d.%m.%Y')
        await query.edit_message_text(text=f"Во сколько нужно напомнить?", reply_markup=InlineKeyboardMarkup([[ 
            InlineKeyboardButton("+1 мин", callback_data='plus_one'), 
            InlineKeyboardButton("+5 мин", callback_data='plus_five') 
        ]]))
    elif query.data == 'tomorrow':
        reminders[user_id][-1]['date'] = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%d.%m.%Y')
        await query.edit_message_text(text=f"Во сколько нужно напомнить?", reply_markup=InlineKeyboardMarkup([[ 
            InlineKeyboardButton("+1 мин", callback_data='plus_one'), 
            InlineKeyboardButton("+5 мин", callback_data='plus_five') 
        ]]))
    elif query.data == 'plus_one':
        reminder_time = (datetime.datetime.now() + datetime.timedelta(minutes=1)).strftime('%H:%M')
        reminders[user_id][-1]['time'] = reminder_time
        await confirm_reminder(update, user_id, reminder_time, context)
    elif query.data == 'plus_five':
        reminder_time = (datetime.datetime.now() + datetime.timedelta(minutes=5)).strftime('%H:%M')
        reminders[user_id][-1]['time'] = reminder_time
        await confirm_reminder(update, user_id, reminder_time, context)

async def confirm_reminder(update: Update, user_id, reminder_time, context):
    reminder = reminders[user_id][-1]
    await update.callback_query.edit_message_text(
        text=f"Отлично! Я напомню тебе **{reminder['text']}** на {reminder['date']} в {reminder['time']}",
        parse_mode="Markdown"
    )

    reminder_datetime = datetime.datetime.strptime(f"{reminder['date']} {reminder_time}", '%d.%m.%Y %H:%M')
    current_time = datetime.datetime.now()

    if reminder_datetime > current_time:
        time_delta = (reminder_datetime - current_time).total_seconds()
        context.job_queue.run_once(send_reminder, when=time_delta, data={
            'chat_id': update.callback_query.message.chat_id,
            'text': reminder['text'],
            'date': reminder['date'],
            'time': reminder['time']
        })
    else:
        await update.callback_query.message.reply_text("Указанное время уже прошло! Пожалуйста, укажи время в будущем")

# Flask приложение для health check
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running"

# Функция для запуска бота и Flask-сервера в отдельных потоках
def run():
    # Запуск бота в отдельном потоке
    from threading import Thread
    Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 8000}).start()

    # Запуск основного бота
    app = Application.builder().token("8074930958:AAF0TEJqjDKnI1QJHSJcE2seK9ccnMpcjDA").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("list", show_reminders))
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Запуск бота
    app.run_polling()

if __name__ == '__main__':
    run()
