import logging
import re
import os
from typing import Dict, Any
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import TELEGRAM_TOKEN, ADMIN_ID, SERVICES, AVAILABLE_SLOTS

# --- Логирование ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Состояния ConversationHandler ---
SELECT_SERVICE, SELECT_SLOT, ENTER_NAME, ENTER_PHONE, CONFIRM = range(5)

# --- Конфиг ---
GOOGLE_SHEETS_CONFIG = {
    'SCOPE': [
        'https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive'
    ],
    'CREDENTIALS_FILE': 'credentials.json',
    'SHEET_NAME': 'Клиенты Косметолога',
    'SHEET_TAB': 'Записи',  # Имя листа внутри таблицы (если понадобится)
}

# --- Google Sheets ---
SCOPE = GOOGLE_SHEETS_CONFIG['SCOPE']
SHEET_NAME = GOOGLE_SHEETS_CONFIG['SHEET_NAME']
CREDENTIALS_FILE = GOOGLE_SHEETS_CONFIG['CREDENTIALS_FILE']

# --- Валидация телефона ---
def validate_phone(phone: str) -> bool:
    # Простой паттерн для РФ: +7XXXXXXXXXX или 8XXXXXXXXXX
    return bool(re.fullmatch(r"(\+7|8)\d{10}", phone))

# --- Google Sheets client ---
def get_gs_client():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPE)
    client = gspread.authorize(creds)
    return client

def save_to_gs(data: Dict[str, Any]):
    try:
        client = get_gs_client()
        sheet = client.open(SHEET_NAME).sheet1
        sheet.append_row([
            data['name'],
            data['phone'],
            data['service'],
            data['slot'],
            data['user_id']
        ])
        logger.info(f"Запись сохранена: {data}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении в Google Sheets: {e}")

# --- Получение занятых слотов из Google Sheets ---
def get_booked_slots(service: str) -> set:
    try:
        client = get_gs_client()
        sheet = client.open(SHEET_NAME).sheet1
        records = sheet.get_all_records()
        return set(row['Дата и время'] for row in records if row['Услуга'] == service)
    except Exception as e:
        logger.error(f"Ошибка при получении занятых слотов: {e}")
        return set()

# --- Старт ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"Пользователь {user.id} начал диалог.")
    keyboard = [[InlineKeyboardButton(service, callback_data=service)] for service in SERVICES]
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    instruction = (
        "👋 Добро пожаловать!\n\n"
        "Я помогу вам быстро и удобно записаться на услуги косметолога.\n\n"
        "1️⃣ Выберите услугу\n"
        "2️⃣ Выберите дату и время\n"
        "3️⃣ Введите имя и телефон\n"
        "4️⃣ Подтвердите запись\n\n"
        "В любой момент вы можете вернуться назад или отменить запись.\n"
        "\nВыберите услугу:")
    await update.message.reply_text(
        instruction,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_SERVICE

# --- Выбор услуги ---
async def select_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service = query.data
    if service == "cancel":
        return await cancel(update, context)
    context.user_data['service'] = service
    logger.info(f"Пользователь выбрал услугу: {service}")
    # Получаем занятые слоты
    booked_slots = get_booked_slots(service)
    slots = AVAILABLE_SLOTS.get(service, [])
    keyboard = []
    for slot in slots:
        if slot in booked_slots:
            keyboard.append([InlineKeyboardButton(f"{slot} ❌ Занято", callback_data="slot_busy")])
        else:
            keyboard.append([InlineKeyboardButton(slot, callback_data=slot)])
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_service"), InlineKeyboardButton("Отмена", callback_data="cancel")])
    await query.edit_message_text(
        f"Вы выбрали: {service}\n\nВыберите дату и время:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_SLOT

# --- Обработчик кнопки 'Назад' с этапа выбора слота ---
async def back_to_service(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton(service, callback_data=service)] for service in SERVICES]
    keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel")])
    await query.edit_message_text(
        "Выберите услугу:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_SERVICE

# --- Выбор даты и времени ---
async def select_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "back_to_service":
        return await back_to_service(update, context)
    if query.data == "cancel":
        return await cancel(update, context)
    if query.data == "slot_busy":
        await query.answer(text="Этот слот уже занят. Пожалуйста, выберите другой!", show_alert=True)
        return SELECT_SLOT
    slot = query.data
    # Проверяем, не занят ли слот прямо сейчас (на случай гонки)
    booked_slots = get_booked_slots(context.user_data['service'])
    if slot in booked_slots:
        await query.answer(text="Этот слот только что заняли. Пожалуйста, выберите другой!", show_alert=True)
        return SELECT_SLOT
    context.user_data['slot'] = slot
    logger.info(f"Пользователь выбрал слот: {slot}")
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_slot"), InlineKeyboardButton("Отмена", callback_data="cancel")]]
    await query.edit_message_text(
        f"Вы выбрали: {context.user_data['service']}\nДата и время: {slot}\n\nПожалуйста, введите ваше имя:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ENTER_NAME

# --- Обработчик кнопки 'Назад' с этапа ввода имени ---
async def back_to_slot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service = context.user_data.get('service')
    slots = AVAILABLE_SLOTS.get(service, [])
    keyboard = [[InlineKeyboardButton(slot, callback_data=slot)] for slot in slots]
    keyboard.append([InlineKeyboardButton("Назад", callback_data="back_to_service"), InlineKeyboardButton("Отмена", callback_data="cancel")])
    await query.edit_message_text(
        f"Вы выбрали: {service}\n\nВыберите дату и время:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECT_SLOT

# --- Ввод имени ---
async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    if not name:
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_slot"), InlineKeyboardButton("Отмена", callback_data="cancel")]]
        await update.message.reply_text(
            "Пожалуйста, введите ваше имя. Это поле не может быть пустым! 😊",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ENTER_NAME
    context.user_data['name'] = name
    logger.info(f"Пользователь ввёл имя: {name}")
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_name"), InlineKeyboardButton("Отмена", callback_data="cancel")]]
    await update.message.reply_text(
        "Пожалуйста, введите ваш номер телефона (например, +79991234567):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ENTER_PHONE

# --- Обработчик кнопки 'Назад' с этапа ввода телефона ---
async def back_to_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"Вы выбрали: {context.user_data.get('service')}\nДата и время: {context.user_data.get('slot')}\n\nПожалуйста, введите ваше имя:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data="back_to_slot"), InlineKeyboardButton("Отмена", callback_data="cancel")]])
    )
    return ENTER_NAME

# --- Ввод телефона ---
async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone = update.message.text.strip()
    if not phone:
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_name"), InlineKeyboardButton("Отмена", callback_data="cancel")]]
        await update.message.reply_text(
            "Пожалуйста, введите номер телефона. Это поле не может быть пустым! 📱",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ENTER_PHONE
    if not validate_phone(phone):
        keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_name"), InlineKeyboardButton("Отмена", callback_data="cancel")]]
        await update.message.reply_text(
            "Похоже, номер телефона введён некорректно. Пример: +79991234567 или 89991234567. Попробуйте ещё раз!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ENTER_PHONE
    context.user_data['phone'] = phone
    logger.info(f"Пользователь ввёл телефон: {phone}")
    summary = (
        f"Проверьте данные:\n"
        f"Услуга: {context.user_data['service']}\n"
        f"Дата и время: {context.user_data['slot']}\n"
        f"Имя: {context.user_data['name']}\n"
        f"Телефон: {context.user_data['phone']}\n\n"
        f"Всё верно?"
    )
    keyboard = [
        [InlineKeyboardButton("Подтвердить", callback_data="confirm")],
        [InlineKeyboardButton("Отмена", callback_data="cancel")],
        [InlineKeyboardButton("Назад", callback_data="back_to_phone")]
    ]
    await update.message.reply_text(summary, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM

# --- Обработчик кнопки 'Назад' с этапа подтверждения ---
async def back_to_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("Назад", callback_data="back_to_name"), InlineKeyboardButton("Отмена", callback_data="cancel")]]
    await query.edit_message_text(
        "Пожалуйста, введите ваш номер телефона (например, +79991234567):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ENTER_PHONE

# --- Обработка текстовых сообщений на этапе подтверждения ---
async def confirm_text_warning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("Подтвердить", callback_data="confirm")],
        [InlineKeyboardButton("Отмена", callback_data="cancel")],
        [InlineKeyboardButton("Назад", callback_data="back_to_phone")]
    ]
    await update.message.reply_text(
        "Пожалуйста, используйте кнопки ниже для подтверждения или отмены записи!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM

# --- Подтверждение ---
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "confirm":
        user_id = query.from_user.id
        data = {
            'name': context.user_data['name'],
            'phone': context.user_data['phone'],
            'service': context.user_data['service'],
            'slot': context.user_data['slot'],
            'user_id': user_id
        }
        save_to_gs(data)
        # Уведомление админу
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"Новая запись!\n"
                f"Услуга: {data['service']}\n"
                f"Дата и время: {data['slot']}\n"
                f"Имя: {data['name']}\n"
                f"Телефон: {data['phone']}\n"
                f"Telegram ID: {user_id}"
            )
        )
        keyboard = [[InlineKeyboardButton("Записаться ещё раз", callback_data="restart")]]
        await query.edit_message_text(
            "🎉 Спасибо! Ваша запись принята. Мы свяжемся с вами для подтверждения.\n\nХотите записаться ещё?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        logger.info(f"Запись подтверждена: {data}")
        return ConversationHandler.END
    elif query.data == "restart":
        # Перезапуск сценария
        await start(update, context)
        return SELECT_SERVICE
    else:
        await query.edit_message_text("Запись отменена.")
        logger.info("Пользователь отменил запись на этапе подтверждения.")
        return ConversationHandler.END

# --- Отмена в любой момент ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    await update.message.reply_text(
        "Запись отменена. Если захотите записаться снова — напишите /start",
        reply_markup=ReplyKeyboardRemove()
    )
    logger.info(f"Пользователь {user.id} отменил запись.")
    return ConversationHandler.END

# --- Ошибка ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling update:", exc_info=context.error)

# --- Основной запуск ---
def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            SELECT_SERVICE: [CallbackQueryHandler(select_service), CallbackQueryHandler(cancel, pattern="^cancel$")],
            SELECT_SLOT: [CallbackQueryHandler(select_slot), CallbackQueryHandler(back_to_service, pattern="^back_to_service$"), CallbackQueryHandler(cancel, pattern="^cancel$")],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name), CallbackQueryHandler(back_to_slot, pattern="^back_to_slot$"), CallbackQueryHandler(cancel, pattern="^cancel$")],
            ENTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone), CallbackQueryHandler(back_to_name, pattern="^back_to_name$"), CallbackQueryHandler(cancel, pattern="^cancel$")],
            CONFIRM: [CallbackQueryHandler(confirm), CallbackQueryHandler(back_to_phone, pattern="^back_to_phone$"), CallbackQueryHandler(cancel, pattern="^cancel$"), MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_text_warning)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_error_handler(error_handler)

    logger.info("Бот запущен.")
    application.run_polling()

if __name__ == '__main__':
    main() 