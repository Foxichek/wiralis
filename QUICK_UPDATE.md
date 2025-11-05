# ⚡ Быстрое обновление WIRALIS на продакшн

## 🚀 Команды для быстрого обновления

### Вариант 1: Если используете Git

```bash
cd /var/www/wiralis.ru
pm2 stop wiralis
git pull origin main
npm install
npm run build
pm2 restart wiralis
pm2 logs wiralis --lines 50
```

### Вариант 2: Ручное копирование файлов

```bash
# На вашем локальном компьютере / Replit
# Создайте архив проекта
tar -czf wiralis-update.tar.gz \
  --exclude=node_modules \
  --exclude=dist \
  --exclude=.git \
  --exclude=.env \
  .

# Скопируйте на сервер
scp wiralis-update.tar.gz user@your-server:/tmp/

# На сервере
cd /var/www
pm2 stop wiralis
sudo rm -rf wiralis.ru.backup
sudo mv wiralis.ru wiralis.ru.backup
sudo mkdir wiralis.ru
cd wiralis.ru
sudo tar -xzf /tmp/wiralis-update.tar.gz
sudo chown -R $USER:$USER /var/www/wiralis.ru

# Копируем .env из старой версии
sudo cp /var/www/wiralis.ru.backup/.env /var/www/wiralis.ru/.env

# Установка и сборка
npm install
npm run db:push
npm run build

# Запуск
pm2 restart wiralis
pm2 logs wiralis --lines 50
```

### Вариант 3: Использование rsync (рекомендуется)

```bash
# На локальном компьютере / Replit
rsync -avz --delete \
  --exclude='node_modules' \
  --exclude='dist' \
  --exclude='.git' \
  --exclude='.env' \
  ./ user@your-server:/var/www/wiralis.ru/

# На сервере
cd /var/www/wiralis.ru
pm2 stop wiralis
npm install
npm run db:push
npm run build
pm2 restart wiralis
pm2 logs wiralis --lines 50
```

## 🔍 Проверка после обновления

```bash
# 1. Проверить статус PM2
pm2 status

# 2. Проверить логи на ошибки
pm2 logs wiralis --lines 100

# 3. Тест API
curl -I https://wiralis.ru/
curl -I https://wiralis.online/

# 4. Проверить фавикон
curl -I https://wiralis.ru/favicon.png

# 5. Тест API генерации кода
curl -X POST https://wiralis.ru/api/bot/generate-code \
  -H "Content-Type: application/json" \
  -H "X-API-Key: US42982557" \
  -d '{"telegramId": 123, "nickname": "Test"}'
```

## ⚠️ В случае проблем - откат назад

```bash
# Остановить текущую версию
pm2 stop wiralis

# Вернуть старую версию
cd /var/www
sudo rm -rf wiralis.ru
sudo mv wiralis.ru.backup wiralis.ru
cd wiralis.ru

# Запустить
pm2 restart wiralis
```

## 📋 Чеклист обновления

- [ ] Остановить приложение (`pm2 stop wiralis`)
- [ ] Сделать бэкап старой версии
- [ ] Скопировать новые файлы
- [ ] Установить зависимости (`npm install`)
- [ ] Обновить БД (`npm run db:push`)
- [ ] Собрать проект (`npm run build`)
- [ ] Запустить приложение (`pm2 restart wiralis`)
- [ ] Проверить логи (`pm2 logs wiralis`)
- [ ] Протестировать API
- [ ] Проверить сайт в браузере
