# Cosmetologist Booking Bot

Telegram-бот для онлайн-записи к косметологу с интеграцией Google Sheets.

## Возможности
- Запись клиентов через Telegram
- Выбор услуги, даты и времени
- Проверка занятости слотов (двойная запись невозможна)
- Все записи сохраняются в Google Sheets
- Удобная навигация: кнопки "Назад", "Отмена", повторная запись
- Дружелюбный UX и сообщения об ошибках

## Скриншот
![image](https://github.com/user-attachments/assets/dea6e024-473b-43a6-99ee-20c1a485d509)
![image](https://github.com/user-attachments/assets/85dfebab-ebee-4374-9f5b-fe793abde19f)
![image](https://github.com/user-attachments/assets/23f126e9-df87-4ea1-90c4-8673dc90824c)
![image](https://github.com/user-attachments/assets/3ca82025-457b-4b9f-8d81-07631df237c1)
![image](https://github.com/user-attachments/assets/d0abff97-be01-482d-b8b6-d7887983a4fe)
![image](https://github.com/user-attachments/assets/0aa123aa-1b87-477b-b94c-4490d109a857)
![image](https://github.com/user-attachments/assets/4c94b412-bb10-4b11-a97d-4e6913a6f21e)


## Быстрый старт

1. **Клонируйте репозиторий:**
   ```sh
   git clone https://github.com/yourusername/cosmetologist-booking-bot.git
   cd cosmetologist-booking-bot
   ```

2. **Установите зависимости:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Создайте Google Service Account и скачайте credentials.json:**
   - Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
   - Создайте проект, включите Google Sheets API и Google Drive API
   - Создайте сервисный аккаунт, скачайте credentials.json
   - Дайте сервисному аккаунту доступ "Редактор" к вашей Google таблице

4. **Скопируйте example_config.py в config.py и заполните:**
   ```sh
   cp example_config.py config.py
   # отредактируйте config.py
   ```

5. **Запустите бота:**
   ```sh
   python main.py
   ```

## Настройки
- Все параметры (токен, ID админа, услуги, доступные слоты) задаются в config.py
- Пример — см. example_config.py

## Как добавить услуги и слоты
- В файле config.py отредактируйте переменные SERVICES и AVAILABLE_SLOTS

## Важно!
- Не добавляйте credentials.json и config.py с реальными токенами в публичный репозиторий!
- Для демонстрации используйте example_config.py

## Зависимости
- python-telegram-bot
- gspread
- oauth2client

## Лицензия
MIT 
