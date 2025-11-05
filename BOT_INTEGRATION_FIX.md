# Исправление интеграции бота с веб-сайтом

## Проблема

Бот получает ошибку:
```
aiohttp.client_exceptions.ContentTypeError: 404, message='Attempt to decode JSON with unexpected mimetype: text/html; charset=utf-8'
```

## Причина

API endpoint `/api/bot/generate-code` принимает только **POST** запросы, но бот может делать **GET** запросы из-за редиректов или неправильной конфигурации.

## Решение

### 1. Обновите URL в боте

В файле `web_module.py` измените URL на актуальный Replit URL:

```python
# В начале файла
WEBSITE_URL = "https://f0c4ed74-74ff-4b49-8bd7-3f8b5f2a0f47-00-1ffnp1j94sgch.picard.replit.dev"
API_SECRET = "US42982557"
```

**ВАЖНО**: Если вы деплоите на VPS, измените на:
```python
WEBSITE_URL = "https://wiralis.ru"
```

### 2. Исправьте функцию generate_code_from_api

Убедитесь, что функция правильно делает POST запрос:

```python
async def generate_code_from_api(user_data: dict) -> dict:
    """
    Асинхронная функция для генерации кода через API сайта.
    """
    try:
        async with aiohttp.ClientSession() as session:
            # ВАЖНО: Используем session.post, не get!
            async with session.post(
                f'{WEBSITE_URL}/api/bot/generate-code',
                json=user_data,  # Передаём данные как JSON
                headers={
                    'X-API-Key': API_SECRET,
                    'Content-Type': 'application/json'
                },
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=False  # НЕ следуем редиректам, чтобы POST не превратился в GET
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_data = await response.json()
                    error_msg = error_data.get('error', 'Неизвестная ошибка')
                    logger.error(f"API error: {response.status} - {error_msg}")
                    return {'error': error_msg, 'status': response.status}
                    
    except aiohttp.ClientTimeout:
        logger.error("API request timeout")
        return {'error': 'timeout'}
    except Exception as e:
        logger.error(f"API request error: {e}", exc_info=True)
        return {'error': 'connection_failed'}
```

### 3. Добавьте логирование для отладки

Добавьте логи перед запросом:

```python
logger.info(f"Отправка POST запроса на {WEBSITE_URL}/api/bot/generate-code")
logger.info(f"Данные пользователя: telegramId={user_data.get('telegramId')}, nickname={user_data.get('nickname')}")
```

### 4. Тестирование API вручную

Вы можете протестировать API из терминала:

```bash
curl -X POST "https://f0c4ed74-74ff-4b49-8bd7-3f8b5f2a0f47-00-1ffnp1j94sgch.picard.replit.dev/api/bot/generate-code" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: US42982557" \
  -d '{
    "telegramId": 123456789,
    "nickname": "TestUser",
    "username": "testuser",
    "quote": "Test quote",
    "botId": "TEST"
  }'
```

Ожидаемый ответ:
```json
{
  "code": "ABC123",
  "expiresAt": "2025-11-05T14:00:00.000Z",
  "message": "Код успешно сгенерирован"
}
```

### 5. Проверьте версию aiohttp

Убедитесь, что используете последнюю версию aiohttp:

```bash
pip install --upgrade aiohttp
```

### 6. Полный исправленный код web_module.py

```python
#!/usr/bin/env python3
"""
Модуль веб-интеграции для WIRALIS бота.
Позволяет пользователям генерировать коды для входа на сайт.
"""

import logging
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes
from sqlalchemy import select
from database import async_session_maker
from models import User

logger = logging.getLogger(__name__)

# Конфигурация
WEBSITE_URL = "https://f0c4ed74-74ff-4b49-8bd7-3f8b5f2a0f47-00-1ffnp1j94sgch.picard.replit.dev"
API_SECRET = "US42982557"

async def generate_code_from_api(user_data: dict) -> dict:
    """
    Асинхронная функция для генерации кода через API сайта.
    """
    try:
        logger.info(f"[WEB MODULE] Отправка POST запроса на {WEBSITE_URL}/api/bot/generate-code")
        logger.info(f"[WEB MODULE] User: {user_data.get('nickname')} (ID: {user_data.get('telegramId')})")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'{WEBSITE_URL}/api/bot/generate-code',
                json=user_data,
                headers={
                    'X-API-Key': API_SECRET,
                    'Content-Type': 'application/json'
                },
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=False  # Не следуем редиректам
            ) as response:
                logger.info(f"[WEB MODULE] Response status: {response.status}")
                logger.info(f"[WEB MODULE] Response content-type: {response.content_type}")
                
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"[WEB MODULE] Success! Code generated: {result.get('code')}")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"[WEB MODULE] API error {response.status}: {error_text}")
                    return {'error': f'HTTP {response.status}', 'status': response.status}
                    
    except aiohttp.ClientTimeout:
        logger.error("[WEB MODULE] API request timeout")
        return {'error': 'timeout'}
    except Exception as e:
        logger.error(f"[WEB MODULE] API request error: {e}", exc_info=True)
        return {'error': 'connection_failed'}

# ... остальной код без изменений ...
```

## Проверка работоспособности

После внесения изменений:

1. Перезапустите бота
2. Отправьте команду `/web` в боте
3. Проверьте логи бота - должны быть сообщения `[WEB MODULE]`
4. Если получаете код - всё работает!

## Для production (VPS)

Когда деплоите на VPS, измените в `web_module.py`:

```python
WEBSITE_URL = "https://wiralis.ru"  # Ваш домен
API_SECRET = "US42982557"  # Тот же секрет
```

И убедитесь, что в `.env` на сервере есть:
```
TELEGRAM_BOT_API_SECRET=US42982557
```
