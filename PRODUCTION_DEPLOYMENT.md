# 🚀 Инструкция по развертыванию WIRALIS на продакшн

## 📋 Предварительные требования

- Node.js 20+ установлен на сервере
- PostgreSQL база данных
- Nginx для обратного прокси
- PM2 для управления процессами Node.js
- Доступ к серверу через SSH

## 🔧 Шаг 1: Подготовка сервера

### Установка зависимостей

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Node.js 20
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs

# Установка PM2
sudo npm install -g pm2

# Установка Nginx (если еще не установлен)
sudo apt install -y nginx
```

## 📦 Шаг 2: Клонирование проекта

```bash
# Переходим в директорию веб-сервера
cd /var/www

# Удаляем старую версию (если есть)
sudo rm -rf wiralis.ru

# Клонируем новую версию из Replit
# ВАЖНО: Замените <YOUR_REPLIT_URL> на ваш URL
git clone <YOUR_REPLIT_GIT_URL> wiralis.ru

# Или копируем файлы вручную через rsync/scp
```

## 🔐 Шаг 3: Настройка переменных окружения

```bash
cd /var/www/wiralis.ru

# Создаем файл .env
sudo nano .env
```

Добавьте следующие переменные:

```env
# База данных PostgreSQL
DATABASE_URL=postgresql://postgres:password@localhost:5432/wiralis

# API секрет для бота
TELEGRAM_BOT_API_SECRET=US42982557

# Окружение
NODE_ENV=production
```

**Сохраните файл:** Ctrl+O, Enter, Ctrl+X

## 📚 Шаг 4: Установка зависимостей и сборка

```bash
# Установка зависимостей
npm install

# Синхронизация схемы базы данных
npm run db:push

# Сборка фронтенда и бэкенда
npm run build
```

## 🚦 Шаг 5: Запуск приложения через PM2

```bash
# Останавливаем старый процесс (если есть)
pm2 delete wiralis 2>/dev/null || true

# Запускаем новое приложение
pm2 start npm --name "wiralis" -- run start

# Сохраняем конфигурацию PM2
pm2 save

# Настраиваем автозапуск при перезагрузке
pm2 startup
# Выполните команду, которую выдаст PM2
```

## 🌐 Шаг 6: Настройка Nginx

### Для wiralis.ru

```bash
sudo nano /etc/nginx/sites-available/wiralis.ru
```

Добавьте конфигурацию:

```nginx
server {
    listen 80;
    server_name wiralis.ru www.wiralis.ru;

    # Редирект на HTTPS (настроить позже с Let's Encrypt)
    # return 301 https://$server_name$request_uri;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Для wiralis.online

```bash
sudo nano /etc/nginx/sites-available/wiralis.online
```

Добавьте ту же конфигурацию, заменив `wiralis.ru` на `wiralis.online`:

```nginx
server {
    listen 80;
    server_name wiralis.online www.wiralis.online;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Активация сайтов

```bash
# Создаем символические ссылки
sudo ln -sf /etc/nginx/sites-available/wiralis.ru /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/wiralis.online /etc/nginx/sites-enabled/

# Проверяем конфигурацию
sudo nginx -t

# Перезапускаем Nginx
sudo systemctl restart nginx
```

## 🔒 Шаг 7: Настройка SSL (HTTPS)

```bash
# Установка Certbot
sudo apt install -y certbot python3-certbot-nginx

# Получение сертификатов для обоих доменов
sudo certbot --nginx -d wiralis.ru -d www.wiralis.ru
sudo certbot --nginx -d wiralis.online -d www.wiralis.online

# Автоматическое обновление сертификатов
sudo systemctl enable certbot.timer
```

## 🔄 Шаг 8: Обновление приложения (после внесения изменений)

```bash
cd /var/www/wiralis.ru

# Останавливаем приложение
pm2 stop wiralis

# Получаем последние изменения (если используете Git)
git pull origin main

# Или копируем файлы вручную

# Устанавливаем зависимости (если изменился package.json)
npm install

# Обновляем схему базы данных (если изменилась)
npm run db:push

# Пересобираем приложение
npm run build

# Запускаем приложение
pm2 restart wiralis

# Проверяем логи
pm2 logs wiralis --lines 50
```

## 📊 Мониторинг и управление

### Полезные команды PM2

```bash
# Просмотр статуса
pm2 status

# Просмотр логов
pm2 logs wiralis

# Просмотр последних 100 строк логов
pm2 logs wiralis --lines 100

# Перезапуск приложения
pm2 restart wiralis

# Остановка приложения
pm2 stop wiralis

# Удаление приложения из PM2
pm2 delete wiralis
```

### Проверка работы Nginx

```bash
# Проверка статуса
sudo systemctl status nginx

# Просмотр логов ошибок
sudo tail -f /var/log/nginx/error.log

# Просмотр логов доступа
sudo tail -f /var/log/nginx/access.log
```

## 🧪 Тестирование API

### Тест генерации кода (от имени бота)

```bash
curl -X POST https://wiralis.ru/api/bot/generate-code \
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
  "expiresAt": "2025-11-05T20:00:00.000Z",
  "message": "Код успешно сгенерирован"
}
```

### Тест проверки кода (от имени сайта)

```bash
curl -X POST https://wiralis.ru/api/verify-code \
  -H "Content-Type: application/json" \
  -d '{"code": "ABC123"}'
```

Ожидаемый ответ:
```json
{
  "success": true,
  "user": {
    "id": "uuid",
    "telegramId": 123456789,
    "nickname": "TestUser",
    ...
  }
}
```

## ⚠️ Устранение неполадок

### Приложение не запускается

```bash
# Проверьте логи PM2
pm2 logs wiralis --err

# Проверьте переменные окружения
pm2 env 0

# Проверьте порт 5000
sudo netstat -tulpn | grep 5000
```

### Ошибка базы данных

```bash
# Проверьте подключение к PostgreSQL
psql -h localhost -U postgres -d wiralis

# Пересоздайте таблицы
npm run db:push --force
```

### Nginx возвращает 502

```bash
# Убедитесь что приложение запущено
pm2 status

# Проверьте логи Nginx
sudo tail -f /var/log/nginx/error.log
```

## 📝 Примечания

1. **Фавикон**: Новый фавикон (`favicon.png`) находится в `client/public/` и автоматически копируется при сборке
2. **База данных**: Используется PostgreSQL. Убедитесь что `DATABASE_URL` правильно настроен
3. **API ключ**: `TELEGRAM_BOT_API_SECRET` должен совпадать с секретом в боте
4. **Порт**: Приложение работает на порту 5000, Nginx проксирует запросы

## 🎉 Готово!

После выполнения всех шагов:
- ✅ Сайт доступен на https://wiralis.ru и https://wiralis.online
- ✅ Фавикон отображается корректно
- ✅ API `/api/bot/generate-code` работает
- ✅ API `/api/verify-code` работает
- ✅ Все ошибки исправлены
