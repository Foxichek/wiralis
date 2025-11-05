# modules/themes_module.py
"""
Модуль управления темами оформления профиля и инвентаря.
Позволяет пользователям разблокировать и применять различные визуальные темы.

Версия 3.0:
- Полная интеграция с profile_module и inventory_module.
- Улучшена функция apply_theme_to_text для корректного применения стилей из JSONB.
- Кнопка управления темами доступна только в личном профиле.
- Добавлена проверка прав доступа в коллбэк меню тем.
- Код полностью адаптирован для работы с новой структурой БД.

Версия 2.0:
- Восстановлена и улучшена интеграция с profile_module.
- Кнопка управления темами добавлена в личный профиль пользователя.
- Добавлена проверка прав доступа в коллбэк меню тем, чтобы оно было доступно только владельцу профиля.
- Код адаптирован для полной совместимости со структурой profile_module.

Версия 1.1:
- Убрана кнопка управления темами из публичного профиля.
- Добавлена более надежная обработка ошибок в коллбэках для предотвращения "зависания" кнопок.
- Поля для accent_color в моделях зарезервированы, но не используются в логике модуля.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes, BaseHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest

from database import async_session_maker
from models import User, ThemeDefinition, UserTheme

if TYPE_CHECKING:
    from main import BotCore

logger = logging.getLogger(__name__)

# ============================================================================
# МЕНЕДЖЕР ТЕМ
# ============================================================================

class ThemeManager:
    """Класс для управления темами оформления."""

    def __init__(self):
        self.themes_cache: Dict[int, ThemeDefinition] = {}
        logger.info("ThemeManager инициализирован.")

    async def load_themes_cache(self):
        """Загружает все темы в кэш."""
        async with async_session_maker() as session:
            result = await session.execute(select(ThemeDefinition).filter_by(is_active=True))
            themes = result.scalars().all()
            self.themes_cache = {theme.id: theme for theme in themes}
            logger.info(f"Загружено {len(self.themes_cache)} тем в кэш.")

    async def get_theme_by_code(self, code_name: str) -> Optional[ThemeDefinition]:
        """Получает тему по кодовому имени."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(ThemeDefinition).filter_by(code_name=code_name, is_active=True)
            )
            return result.scalar_one_or_none()

    async def get_theme_by_id(self, theme_id: int) -> Optional[ThemeDefinition]:
        """Получает тему по ID."""
        if theme_id in self.themes_cache:
            return self.themes_cache[theme_id]

        async with async_session_maker() as session:
            return await session.get(ThemeDefinition, theme_id)

    async def unlock_theme_for_user(self, user_id: int, theme_id: int) -> Tuple[bool, str]:
        """Разблокирует тему для пользователя."""
        async with async_session_maker() as session:
            async with session.begin():
                theme = await session.get(ThemeDefinition, theme_id)
                if not theme:
                    return False, "ТЕМА НЕ НАЙДЕНА."

                stmt = pg_insert(UserTheme).values(
                    user_telegram_id=user_id,
                    theme_id=theme_id
                )
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=['user_telegram_id', 'theme_id']
                )
                await session.execute(stmt)

                logger.info(f"Пользователь {user_id} разблокировал тему {theme.code_name}")
                return True, f"🎨 РАЗБЛОКИРОВАНО ОФОРМЛЕНИЕ: {theme.display_name}"

    async def apply_theme_for_user(self, user_id: int, theme_id: Optional[int]) -> Tuple[bool, str]:
        """Применяет тему для пользователя."""
        async with async_session_maker() as session:
            async with session.begin():
                user_result = await session.execute(select(User).filter_by(telegram_id=user_id))
                user = user_result.scalar_one_or_none()
                if not user:
                    return False, "ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН."

                if theme_id is None:
                    user.active_theme_id = None
                    logger.info(f"Пользователь {user_id} сбросил тему на стандартную.")
                    return True, "🎨 УСТАНОВЛЕНО СТАНДАРТНОЕ ОФОРМЛЕНИЕ."

                has_theme_result = await session.execute(
                    select(UserTheme).filter_by(user_telegram_id=user_id, theme_id=theme_id)
                )
                if not has_theme_result.scalar_one_or_none():
                    return False, "ВЫ НЕ РАЗБЛОКИРОВАЛИ ЭТУ ТЕМУ."

                theme = await session.get(ThemeDefinition, theme_id)
                if not theme or not theme.is_active:
                    return False, "ТЕМА НЕДОСТУПНА."

                user.active_theme_id = theme_id
                logger.info(f"Пользователь {user_id} применил тему {theme.code_name}")
                return True, f"🎨 ПРИМЕНЕНО ОФОРМЛЕНИЕ: {theme.display_name}"

    async def get_user_unlocked_themes(self, user_id: int) -> List[ThemeDefinition]:
        """Получает список разблокированных тем пользователя."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(ThemeDefinition)
                .join(UserTheme, ThemeDefinition.id == UserTheme.theme_id)
                .filter(UserTheme.user_telegram_id == user_id, ThemeDefinition.is_active == True)
                .order_by(ThemeDefinition.rarity, ThemeDefinition.display_name)
            )
            return result.scalars().all()

    async def get_user_active_theme(self, user_id: int) -> Optional[ThemeDefinition]:
        """Получает активную тему пользователя."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(User).filter_by(telegram_id=user_id)
            )
            user = result.scalar_one_or_none()
            if not user or not user.active_theme_id:
                return None
            
            return await self.get_theme_by_id(user.active_theme_id)


theme_manager = ThemeManager()

# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def apply_theme_to_text(text: str, theme: Optional[ThemeDefinition], context: str) -> str:
    """
    Применяет стилизацию темы к тексту.
    
    Args:
        text: Исходный текст для стилизации
        theme: Объект темы (ThemeDefinition) или None для стандартного оформления
        context: Контекст применения ('profile' или 'inventory')
    
    Returns:
        Стилизованный текст с примененными эффектами темы
    """
    if not theme:
        return text

    styles = theme.profile_styles if context == 'profile' else theme.inventory_styles
    if not styles or not isinstance(styles, dict):
        return text

    result = text
    
    header_emoji = styles.get('header_emoji', '')
    footer_emoji = styles.get('footer_emoji', '')
    separator = styles.get('separator', '')
    
    if header_emoji:
        result = f"{header_emoji}\n{result}"
    
    if footer_emoji:
        result = f"{result}\n{footer_emoji}"
    
    if separator:
        result = result.replace('\n\n', f'\n{separator}\n')
    
    return result

# ============================================================================
# ОБРАБОТЧИКИ КОМАНД
# ============================================================================

async def themes_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает меню управления темами.
    Доступно только владельцу профиля благодаря проверке прав.
    """
    query = update.callback_query
    user_id = query.from_user.id
    
    if '_' in query.data:
        try:
            owner_id = int(query.data.split('_')[-1])
            if user_id != owner_id:
                await query.answer("[CMOS]: ЭТО МЕНЮ ПРЕДНАЗНАЧЕНО ДЛЯ ДРУГОГО ПОЛЬЗОВАТЕЛЯ.", show_alert=True)
                return
        except (ValueError, IndexError):
            await query.answer("ОШИБКА: НЕВЕРНЫЙ ФОРМАТ ДАННЫХ.", show_alert=True)
            logger.warning(f"Не удалось извлечь owner_id из callback_data: {query.data}")
            return
            
    try:
        await query.answer()
        unlocked_themes = await theme_manager.get_user_unlocked_themes(user_id)
        active_theme = await theme_manager.get_user_active_theme(user_id)

        if not unlocked_themes:
            text = "<b>[CMOS]: УПРАВЛЕНИЕ ТЕМАМИ</b>\n\nУ вас пока нет разблокированных тем оформления."
            keyboard = [[InlineKeyboardButton("« Назад в профиль", callback_data=f"profile_back_self_{user_id}")]]
        else:
            text = "<b>[CMOS]: УПРАВЛЕНИЕ ТЕМАМИ</b>\n\n"
            text += f"Активная тема: <b>{active_theme.display_name if active_theme else 'Стандартная'}</b>\n\n"
            text += "<b>Ваши темы:</b>\n"

            keyboard = []
            for theme in unlocked_themes:
                is_active = active_theme and active_theme.id == theme.id
                emoji = "✅" if is_active else theme.emoji
                button_text = f"{emoji} {theme.display_name}"
                
                callback_data = "dummy_callback" if is_active else f"theme_apply_{theme.id}"
                
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=callback_data)
                ])

            keyboard.append([InlineKeyboardButton("🔄 Сбросить на стандартную", callback_data="theme_reset")])
            keyboard.append([InlineKeyboardButton("« Назад в профиль", callback_data=f"profile_back_self_{user_id}")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query.message:
            await query.message.delete()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

    except BadRequest as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Ошибка BadRequest при показе меню тем: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в themes_menu_callback: {e}", exc_info=True)
        try:
            await query.answer("Произошла ошибка при загрузке меню.", show_alert=True)
        except Exception as e_inner:
            logger.error(f"Не удалось отправить сообщение об ошибке пользователю: {e_inner}", exc_info=True)


async def theme_apply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Применяет выбранную тему."""
    query = update.callback_query
    try:
        user_id = query.from_user.id
        theme_id = int(query.data.split('_')[-1])

        success, message = await theme_manager.apply_theme_for_user(user_id, theme_id)
        await query.answer(message, show_alert=True)
        
        if success:
            query.data = f"themes_menu_{user_id}" 
            await themes_menu_callback(update, context)

    except Exception as e:
        logger.error(f"Непредвиденная ошибка в theme_apply_callback: {e}", exc_info=True)
        await query.answer("Произошла ошибка при применении темы.", show_alert=True)


async def theme_reset_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сбрасывает тему на стандартную."""
    query = update.callback_query
    try:
        user_id = query.from_user.id
        success, message = await theme_manager.apply_theme_for_user(user_id, None)

        await query.answer(message, show_alert=True)

        if success:
            query.data = f"themes_menu_{user_id}"
            await themes_menu_callback(update, context)
            
    except Exception as e:
        logger.error(f"Непредвиденная ошибка в theme_reset_callback: {e}", exc_info=True)
        await query.answer("Произошла ошибка при сбросе темы.", show_alert=True)

# ============================================================================
# БЛОК ДЛЯ ПРОФИЛЯ
# ============================================================================

async def get_theme_profile_block(telegram_id: int) -> Optional[Dict]:
    """
    Формирует информационный блок о текущей теме для профиля.
    Для личного профиля предоставляет кнопку для входа в меню управления темами.
    """
    try:
        active_theme = await theme_manager.get_user_active_theme(telegram_id)

        if active_theme:
            content = f"{active_theme.emoji} {active_theme.display_name}"
        else:
            content = "Стандартная"
        
        buttons = [[
            InlineKeyboardButton("Меню оформления", callback_data="themes_menu")
        ]]
        
        return {'content': content, 'buttons': buttons}
        
    except Exception as e:
        logger.error(f"Ошибка при создании блока тем для профиля {telegram_id}: {e}", exc_info=True)
        return None

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ
# ============================================================================

def setup(core: 'BotCore') -> Tuple[List[BaseHandler], List[str]]:
    """Инициализация модуля тем."""
    import asyncio
    asyncio.create_task(theme_manager.load_themes_cache())

    try:
        from profile_module import profile_manager
        profile_manager.register_block("theme_info", get_theme_profile_block, "🎨 ОФОРМЛЕНИЕ", 60)
        logger.info("Блок тем зарегистрирован в profile_module.")
    except (ImportError, AttributeError) as e:
        logger.warning(f"Не удалось зарегистрировать блок в profile_module: {e}")

    handlers = [
        CallbackQueryHandler(themes_menu_callback, pattern="^themes_menu"),
        CallbackQueryHandler(theme_apply_callback, pattern="^theme_apply_"),
        CallbackQueryHandler(theme_reset_callback, pattern="^theme_reset$"),
        CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^dummy_callback$")
    ]

    logger.info("Модуль тем инициализирован.")
    return handlers, []

def cleanup(core: 'BotCore'):
    """Выгрузка модуля тем."""
    try:
        from profile_module import profile_manager
        profile_manager.unregister_block("theme_info")
        logger.info("Блок тем удален из profile_module.")
    except (ImportError, AttributeError):
        pass

    logger.info("Модуль тем выгружен.")