import { type WiralisUser, type InsertWiralisUser, type RegistrationCode } from "@shared/schema";

// Storage interface для работы с данными WIRALIS
export interface IStorage {
  // Управление пользователями
  getWiralisUser(id: string): Promise<WiralisUser | undefined>;
  getWiralisUserByTelegramId(telegramId: number): Promise<WiralisUser | undefined>;
  createWiralisUser(user: InsertWiralisUser): Promise<WiralisUser>;
  
  // Управление кодами регистрации
  getRegistrationCode(code: string): Promise<RegistrationCode | undefined>;
  createRegistrationCode(registrationCode: RegistrationCode): Promise<RegistrationCode>;
  markCodeAsUsed(code: string): Promise<void>;
}

export class MemStorage implements IStorage {
  private wiralisUsers: Map<string, WiralisUser>;
  private registrationCodes: Map<string, RegistrationCode>;

  constructor() {
    this.wiralisUsers = new Map();
    this.registrationCodes = new Map();
  }

  async getWiralisUser(id: string): Promise<WiralisUser | undefined> {
    return this.wiralisUsers.get(id);
  }

  async getWiralisUserByTelegramId(telegramId: number): Promise<WiralisUser | undefined> {
    return Array.from(this.wiralisUsers.values()).find(
      (user) => user.telegramId === telegramId,
    );
  }

  async createWiralisUser(insertUser: InsertWiralisUser): Promise<WiralisUser> {
    const id = Math.random().toString(36).substring(2, 15);
    const user: WiralisUser = { 
      id,
      telegramId: insertUser.telegramId,
      nickname: insertUser.nickname,
      username: insertUser.username ?? null,
      quote: insertUser.quote ?? null,
      botId: insertUser.botId ?? null,
      registeredAt: new Date()
    };
    this.wiralisUsers.set(id, user);
    return user;
  }

  async getRegistrationCode(code: string): Promise<RegistrationCode | undefined> {
    return this.registrationCodes.get(code);
  }

  async createRegistrationCode(registrationCode: RegistrationCode): Promise<RegistrationCode> {
    this.registrationCodes.set(registrationCode.code, registrationCode);
    return registrationCode;
  }

  async markCodeAsUsed(code: string): Promise<void> {
    const regCode = this.registrationCodes.get(code);
    if (regCode) {
      regCode.isUsed = true;
      regCode.usedAt = new Date();
      this.registrationCodes.set(code, regCode);
    }
  }
}

export const storage = new MemStorage();
