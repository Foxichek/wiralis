# modules/badges_module.py
"""
Модуль для управления системой бейджей.
Содержит как внутреннее API для выдачи и проверки бейджей,
так и UI-компоненты для управления ими через профиль пользователя.
"""

import logging
from typing import Optional, Tuple, Dict, Any, List, TYPE_CHECKING
from sqlalchemy import select, update
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import BaseHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import BadRequest, Forbidden

# Импортируем общие компоненты из основного модуля профиля
from .profile_module import ProfileBlockManager, _is_allowed, get_user_data, _display_profile

if TYPE_CHECKING:
    from main import BotCore

from database import async_session_maker
from models import User, BadgeDefinition, UserBadge

logger = logging.getLogger(__name__)

# ============================================================================
# API ФУНКЦИИ (для использования другими модулями)
# ============================================================================

async def get_badge_by_code(code_name: str) -> Optional[BadgeDefinition]:
    """Получает определение бейджа по его строковому коду."""
    async with async_session_maker() as session:
        result = await session.execute(
            select(BadgeDefinition).filter_by(code_name=code_name, is_active=True)
        )
        return result.scalar_one_or_none()


async def award_badge(user_id: int, badge_code: str, context: Optional[str] = None) -> Tuple[bool, str]:
    """
    Выдает бейдж пользователю по коду бейджа. Проверяет на дубликаты.
    
    Args:
        user_id: Telegram ID пользователя.
        badge_code: Строковый код бейджа (например, 'newbie').
        context: Опциональный контекст получения (например, 'За регистрацию').
        
    Returns:
        Кортеж (успех, сообщение для пользователя).
    """
    async with async_session_maker() as session:
        async with session.begin():
            badge = await get_badge_by_code(badge_code)
            if not badge:
                logger.error(f"Попытка выдать несуществующий или неактивный бейдж '{badge_code}'")
                return False, "[CMOS]: ОШИБКА: ТАКОЙ БЕЙДЖ НЕ НАЙДЕН."

            result = await session.execute(
                select(UserBadge).filter_by(user_telegram_id=user_id, badge_id=badge.id)
            )
            if result.scalar_one_or_none():
                logger.warning(f"Попытка повторно выдать бейдж '{badge_code}' пользователю {user_id}")
                return False, f"[CMOS]: У ВАС УЖЕ ЕСТЬ БЕЙДЖ {badge.emoji}!"

            new_user_badge = UserBadge(user_telegram_id=user_id, badge_id=badge.id, unlock_context=context)
            session.add(new_user_badge)
            
            logger.info(f"Бейдж '{badge_code}' ({badge.display_name}) выдан пользователю {user_id}")
            return True, f"🏆 ПОЛУЧЕН НОВЫЙ БЕЙДЖ: {badge.emoji} {badge.display_name.upper()}!"


async def has_badge(user_id: int, badge_code: str) -> bool:
    """Проверяет, есть ли у пользователя указанный бейдж."""
    async with async_session_maker() as session:
        badge = await get_badge_by_code(badge_code)
        if not badge:
            return False

        result = await session.execute(
            select(UserBadge.id).filter_by(user_telegram_id=user_id, badge_id=badge.id)
        )
        return result.scalar_one_or_none() is not None


async def set_active_badge(user_id: int, badge_id: Optional[int]) -> Tuple[bool, str]:
    """
    Устанавливает активный бейдж пользователя или снимает его.
    
    Args:
        user_id: Telegram ID пользователя.
        badge_id: ID бейджа из таблицы `badge_definitions` или None для снятия.
        
    Returns:
        Кортеж (успех, сообщение для пользователя).
    """
    async with async_session_maker() as session:
        async with session.begin():
            if badge_id is not None:
                # Проверяем, что у пользователя действительно есть этот бейдж
                result = await session.execute(
                    select(UserBadge.id).filter_by(user_telegram_id=user_id, badge_id=badge_id)
                )
                if not result.scalar_one_or_none():
                    return False, "[CMOS]: У ВАС НЕТ ЭТОГО БЕЙДЖА."

            # Обновляем поле active_badge_id в таблице User
            stmt = update(User).where(User.telegram_id == user_id).values(active_badge_id=badge_id)
            await session.execute(stmt)
            
            if badge_id is None:
                logger.info(f"Пользователь {user_id} снял активный бейдж.")
                return True, "АКТИВНЫЙ БЕЙДЖ СНЯТ."
            
            logger.info(f"Пользователь {user_id} установил активный бейдж (ID: {badge_id}).")
            return True, "АКТИВНЫЙ БЕЙДЖ УСТАНОВЛЕН."


async def get_active_badge(user_id: int) -> Optional[Dict[str, Any]]:
    """Получает полную информацию об активном бейдже пользователя."""
    async with async_session_maker() as session:
        active_badge_id = await session.scalar(
            select(User.active_badge_id).filter_by(telegram_id=user_id)
        )
        if not active_badge_id:
            return None

        badge = await session.scalar(
            select(BadgeDefinition).filter_by(id=active_badge_id, is_active=True)
        )
        if not badge:
            return None
            
        return {'id': badge.id, 'display_name': badge.display_name, 'emoji': badge.emoji}


async def get_active_badge_emoji(user_id: int) -> Optional[str]:
    """Быстро получает только эмодзи активного бейджа."""
    badge_info = await get_active_badge(user_id)
    return badge_info['emoji'] if badge_info else None


async def get_user_badges(user_id: int) -> List[Dict[str, Any]]:
    """Получает список всех бейджей, разблокированных пользователем."""
    async with async_session_maker() as session:
        stmt = (
            select(BadgeDefinition.id, BadgeDefinition.display_name, BadgeDefinition.emoji)
            .join(UserBadge, UserBadge.badge_id == BadgeDefinition.id)
            .where(UserBadge.user_telegram_id == user_id, BadgeDefinition.is_active == True)
            .order_by(BadgeDefinition.display_name)
        )
        result = await session.execute(stmt)
        return [dict(row._mapping) for row in result.all()]

# ============================================================================
# UI-ЧАСТЬ ДЛЯ ИНТЕГРАЦИИ С ПРОФИЛЕМ
# ============================================================================

async def get_badges_profile_block(telegram_id: int) -> Optional[Dict]:
    """Формирует блок профиля для отображения и управления бейджами."""
    active_badge = await get_active_badge(telegram_id)
    
    if active_badge:
        content = f"Активный: {active_badge['emoji']} {active_badge['display_name']}"
    else:
        content = "Активный бейдж не выбран."
        
    buttons = [[InlineKeyboardButton("🏆 Управлять", callback_data="profile_manage_badges")]]
    
    return {'content': content, 'buttons': buttons}


async def badges_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает меню для выбора активного бейджа."""
    query = update.callback_query
    allowed_user_id = int(query.data.split('_')[-1])

    if not await _is_allowed(update, allowed_user_id):
        return
        
    await query.answer()

    user_badges = await get_user_badges(allowed_user_id)
    text = "<b>[CMOS]: УПРАВЛЕНИЕ БЕЙДЖАМИ</b>\n\nВыберите бейдж, который хотите отображать в профиле:"
    keyboard = []

    if not user_badges:
        text += "\n\n<i>У вас пока нет ни одного бейджа.</i>"
    else:
        for badge in user_badges:
            button = InlineKeyboardButton(
                f"{badge['emoji']} {badge['display_name']}",
                callback_data=f"profile_set_badge_{badge['id']}_{allowed_user_id}"
            )
            keyboard.append([button])

    keyboard.append([InlineKeyboardButton("🚫 Снять бейдж", callback_data=f"profile_set_badge_remove_{allowed_user_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к профилю", callback_data=f"profile_back_self_{allowed_user_id}")])
    
    # Используем метод "удалить-и-отправить", чтобы избежать ошибок редактирования
    try:
        await query.message.delete()
    except (BadRequest, Forbidden) as e:
        logger.warning(f"Не удалось удалить сообщение при открытии меню бейджей: {e}")
        
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )


async def set_active_badge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает установку или снятие активного бейджа."""
    query = update.callback_query
    parts = query.data.split('_')
    allowed_user_id = int(parts[-1])
    badge_id_str = parts[3]

    if not await _is_allowed(update, allowed_user_id):
        return

    badge_id = None if badge_id_str == "remove" else int(badge_id_str)
    
    success, message = await set_active_badge(allowed_user_id, badge_id)
    await query.answer(message, show_alert=True)
    
    # Обновляем меню управления, чтобы пользователь сразу увидел изменения
    if success:
        await badges_management_callback(update, context)

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ МОДУЛЯ
# ============================================================================

def register_profile_block(profile_manager: ProfileBlockManager):
    """Регистрирует блок бейджей в основном модуле профиля."""
    profile_manager.register_block("profile_badges", get_badges_profile_block, "🏅 БЕЙДЖИ", 70)

def get_handlers() -> List[BaseHandler]:
    """Возвращает список обработчиков, специфичных для этого модуля."""
    return [
        CallbackQueryHandler(badges_management_callback, pattern=r"^profile_manage_badges_"),
        CallbackQueryHandler(set_active_badge_callback, pattern=r"^profile_set_badge_"),
    ]

def setup(core: 'BotCore') -> Tuple[List[BaseHandler], List[str]]:
    """
    Инициализация модуля бейджей.
    Возвращает обработчики для интеграции с ядром бота.
    """
    logger.info("Модуль управления бейджами инициализирован.")
    return get_handlers(), [] # У этого модуля нет своих команд верхнего уровня

def cleanup():
    """Выгрузка модуля бейджей."""
    logger.info("Модуль управления бейджами выгружен.")