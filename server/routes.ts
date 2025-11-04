import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { db } from "./db";
import { registrationCodes, wiralisUsers } from "@shared/schema";
import { eq, and } from "drizzle-orm";
import { z } from "zod";

// Middleware для проверки API ключа бота
function verifyBotApiKey(req: any, res: any, next: any) {
  const apiKey = req.headers['x-api-key'];
  const expectedKey = process.env.TELEGRAM_BOT_API_SECRET;
  
  if (!apiKey || apiKey !== expectedKey) {
    return res.status(401).json({ error: "Неавторизованный доступ" });
  }
  
  next();
}

export async function registerRoutes(app: Express): Promise<Server> {
  // API для генерации кода регистрации (вызывается ботом)
  app.post("/api/bot/generate-code", verifyBotApiKey, async (req, res) => {
    try {
      const { telegramId, nickname, username, quote, botId } = req.body;
      
      if (!telegramId || !nickname) {
        return res.status(400).json({ error: "telegramId и nickname обязательны" });
      }

      // Генерируем случайный 6-значный код из латинских букв и цифр
      const code = Array.from({ length: 6 }, () => 
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'[Math.floor(Math.random() * 36)]
      ).join('');

      // Код действителен 10 минут
      const expiresAt = new Date(Date.now() + 10 * 60 * 1000);

      // Сохраняем код в базу данных
      const [newCode] = await db.insert(registrationCodes).values({
        code,
        telegramId,
        expiresAt,
        isUsed: false,
      }).returning();

      // Сохраняем или обновляем данные пользователя для будущего импорта
      const existingUser = await db.query.wiralisUsers.findFirst({
        where: eq(wiralisUsers.telegramId, telegramId)
      });

      if (existingUser) {
        // Обновляем существующие данные
        await db.update(wiralisUsers)
          .set({ nickname, username, quote, botId })
          .where(eq(wiralisUsers.telegramId, telegramId));
      } else {
        // Создаем новую запись
        await db.insert(wiralisUsers).values({
          telegramId,
          nickname,
          username: username || null,
          quote: quote || null,
          botId: botId || null,
        });
      }

      res.json({ 
        code, 
        expiresAt: expiresAt.toISOString(),
        message: "Код успешно сгенерирован" 
      });

    } catch (error: any) {
      console.error("Ошибка при генерации кода:", error);
      res.status(500).json({ error: "Ошибка сервера при генерации кода" });
    }
  });

  // API для проверки кода и получения данных пользователя (вызывается сайтом)
  app.post("/api/verify-code", async (req, res) => {
    try {
      const { code } = req.body;

      if (!code || typeof code !== 'string' || code.length !== 6) {
        return res.status(400).json({ error: "Некорректный формат кода" });
      }

      // Ищем код в базе данных
      const regCodeResult = await db.select()
        .from(registrationCodes)
        .where(eq(registrationCodes.code, code.toUpperCase()))
        .limit(1);

      if (!regCodeResult || regCodeResult.length === 0) {
        return res.status(404).json({ error: "Код не найден" });
      }

      const regCode = regCodeResult[0];

      // Проверяем, не истек ли код
      if (new Date() > regCode.expiresAt) {
        return res.status(400).json({ error: "Код истек. Получите новый код в боте командой /web" });
      }

      // Проверяем, не использован ли уже код
      if (regCode.isUsed) {
        return res.status(400).json({ error: "Код уже использован" });
      }

      // Получаем данные пользователя
      const userResult = await db.select()
        .from(wiralisUsers)
        .where(eq(wiralisUsers.telegramId, regCode.telegramId))
        .limit(1);

      if (!userResult || userResult.length === 0) {
        return res.status(404).json({ error: "Данные пользователя не найдены" });
      }

      const user = userResult[0];

      // Помечаем код как использованный
      await db.update(registrationCodes)
        .set({ isUsed: true, usedAt: new Date() })
        .where(eq(registrationCodes.code, code.toUpperCase()));

      // Возвращаем данные пользователя
      res.json({
        success: true,
        user: {
          id: user.id,
          telegramId: user.telegramId,
          nickname: user.nickname,
          username: user.username,
          quote: user.quote,
          botId: user.botId,
        }
      });

    } catch (error: any) {
      console.error("Ошибка при проверке кода:", error);
      res.status(500).json({ error: "Ошибка сервера при проверке кода" });
    }
  });

  // API для получения профиля пользователя
  app.get("/api/profile/:userId", async (req, res) => {
    try {
      const { userId } = req.params;

      const user = await db.query.wiralisUsers.findFirst({
        where: eq(wiralisUsers.id, userId)
      });

      if (!user) {
        return res.status(404).json({ error: "Пользователь не найден" });
      }

      res.json({
        id: user.id,
        nickname: user.nickname,
        username: user.username,
        quote: user.quote,
        botId: user.botId,
        registeredAt: user.registeredAt,
      });

    } catch (error: any) {
      console.error("Ошибка при получении профиля:", error);
      res.status(500).json({ error: "Ошибка сервера" });
    }
  });

  const httpServer = createServer(app);

  return httpServer;
}
