# modules/profile_module.py
"""
Модуль для отображения профиля пользователя.
Собирает информацию из других модулей через систему регистрации блоков.
Поддерживает частные и публичные профили, систему рейтинга и тренды.
Добавлен функционал редактирования цитаты профиля, поиска случайного профиля
и система "Профиль дня" с ежедневной рассылкой.
Интегрирован просмотр постов пользователя.
Добавлена система баннеров профиля.
Интегрирована система тем и бейджей.
"""

import logging
import random
import json
import asyncio
import html
from datetime import date, time
from typing import Dict, List, Optional, Callable, Coroutine, Any, Tuple, TYPE_CHECKING
from uuid import uuid4

import pytz
from sqlalchemy import select, func, update, or_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters, InlineQueryHandler
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest

from database import async_session_maker
from models import User, UserRating, BotState

from registration_module import generate_profile_deeplink, get_profile_visibility

if TYPE_CHECKING:
    from main import BotCore

logger = logging.getLogger(__name__)

AWAITING_QUOTE, AWAITING_BANNER_URL, AWAITING_BANNER_CONFIRMATION = range(3)

PROFILE_OF_THE_DAY_KEY = "profile_of_the_day"


class DatabaseManager:
    """Класс для инкапсуляции всех асинхронных запросов к БД."""

    def __init__(self, session_maker):
        self.async_session_maker = session_maker

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Получает объект пользователя по его ID в Telegram."""
        async with self.async_session_maker() as session:
            result = await session.execute(select(User).filter_by(telegram_id=telegram_id))
            return result.scalar_one_or_none()

    async def get_user_data(self, telegram_id: int) -> Optional[Dict]:
        """Получает данные пользователя в виде словаря."""
        user = await self.get_user_by_telegram_id(telegram_id)
        if user:
            return {c.name: getattr(user, c.name) for c in user.__table__.columns}
        return None

    async def get_user_role(self, telegram_id: int) -> Optional[str]:
        """Получает роль пользователя."""
        user = await self.get_user_by_telegram_id(telegram_id)
        return user.role if user else None

    async def update_user_field(self, telegram_id: int, field: str, value: Any) -> bool:
        """Обновляет одно поле пользователя."""
        async with self.async_session_maker() as session:
            stmt = update(User).where(User.telegram_id == telegram_id).values({field: value})
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def find_user_by_identifier(self, identifier: str) -> Optional[Dict]:
        """Ищет пользователя по bot_id, никнейму, юзернейму или telegram_id."""
        async with self.async_session_maker() as session:
            clean_identifier = identifier.lstrip('@')
            
            # Проверяем, является ли идентификатор числом (для поиска по telegram_id)
            try:
                telegram_id_identifier = int(identifier)
            except ValueError:
                telegram_id_identifier = None

            conditions = [
                User.bot_id == identifier,
                User.nickname.ilike(identifier),
                User.username.ilike(clean_identifier)
            ]
            if telegram_id_identifier is not None:
                conditions.append(User.telegram_id == telegram_id_identifier)

            stmt = select(User).where(or_(*conditions))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                return await self.get_user_data(user.telegram_id)
        return None

    async def get_random_user(self) -> Optional[Dict]:
        """Возвращает случайного пользователя."""
        async with self.async_session_maker() as session:
            stmt = select(User).order_by(func.random()).limit(1)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            if user:
                return await self.get_user_data(user.telegram_id)
        return None

    async def get_user_rating_and_rank(self, telegram_id: int) -> Tuple[int, str, Optional[int]]:
        """Вычисляет рейтинг, категорию и ранг пользователя с учетом уникальности места."""
        async with self.async_session_maker() as session:
            rating_stmt = select(func.sum(UserRating.vote_type)).where(UserRating.target_telegram_id == telegram_id)
            user_rating_result = await session.execute(rating_stmt)
            rating = user_rating_result.scalar_one_or_none() or 0

            if rating == 0:
                return 0, 'neutral', None

            rating_subq = (
                select(
                    UserRating.target_telegram_id.label("user_id"),
                    func.sum(UserRating.vote_type).label("total_rating"),
                    func.max(UserRating.created_at).label("last_vote_time")
                )
                .group_by(UserRating.target_telegram_id)
                .subquery()
            )

            category = 'hype' if rating > 0 else 'antihype'
            
            if category == 'hype':
                order_by_clause = [rating_subq.c.total_rating.desc(), rating_subq.c.last_vote_time.desc()]
                filter_clause = rating_subq.c.total_rating > 0
            else:
                order_by_clause = [rating_subq.c.total_rating.asc(), rating_subq.c.last_vote_time.desc()]
                filter_clause = rating_subq.c.total_rating < 0

            rank_subq = (
                select(
                    rating_subq.c.user_id,
                    func.row_number().over(order_by=order_by_clause).label("rank")
                )
                .where(filter_clause)
                .subquery()
            )

            final_stmt = select(rank_subq.c.rank).where(rank_subq.c.user_id == telegram_id)
            rank_result = await session.execute(final_stmt)
            rank = rank_result.scalar_one_or_none()

            return rating, category, rank

    async def get_trends(self, limit: int = 10, is_antihype: bool = False) -> List[Dict]:
        """Получает топ пользователей для трендов или анти-трендов с уникальным ранжированием."""
        async with self.async_session_maker() as session:
            rating_sum = func.sum(UserRating.vote_type).label("rating")
            last_vote_time = func.max(UserRating.created_at)

            query = (
                select(User.nickname, User.bot_id, User.telegram_id, rating_sum)
                .join(UserRating, User.telegram_id == UserRating.target_telegram_id)
                .group_by(User.telegram_id, User.nickname, User.bot_id)
            )

            if is_antihype:
                query = query.having(rating_sum < 0).order_by(rating_sum.asc(), last_vote_time.desc())
            else:
                query = query.having(rating_sum > 0).order_by(rating_sum.desc(), last_vote_time.desc())

            result = await session.execute(query.limit(limit))
            return [
                {"nickname": row.nickname, "bot_id": row.bot_id, "rating": row.rating, "telegram_id": row.telegram_id}
                for row in result.all()
            ]

    async def get_extreme_ratings(self) -> Dict[str, Optional[Dict]]:
        """Находит пользователей с самым высоким и самым низким рейтингом."""
        async with self.async_session_maker() as session:
            rating_subq = (
                select(
                    UserRating.target_telegram_id.label("user_id"),
                    func.sum(UserRating.vote_type).label("rating")
                )
                .group_by(UserRating.target_telegram_id)
                .cte("ratings")
            )

            highest_rating = (await session.execute(select(func.max(rating_subq.c.rating)))).scalar()
            lowest_rating = (await session.execute(select(func.min(rating_subq.c.rating)))).scalar()

            extremes = {'highest': None, 'lowest': None}

            if highest_rating is not None and highest_rating != 0:
                user_alias = aliased(User)
                h_stmt = select(user_alias.nickname, user_alias.bot_id, rating_subq.c.rating).join(
                    user_alias, user_alias.telegram_id == rating_subq.c.user_id
                ).where(rating_subq.c.rating == highest_rating).limit(1)
                highest_res = (await session.execute(h_stmt)).first()
                if highest_res: extremes['highest'] = dict(highest_res._mapping)

            if lowest_rating is not None and lowest_rating != 0:
                user_alias = aliased(User)
                l_stmt = select(user_alias.nickname, user_alias.bot_id, rating_subq.c.rating).join(
                    user_alias, user_alias.telegram_id == rating_subq.c.user_id
                ).where(rating_subq.c.rating == lowest_rating).limit(1)
                lowest_res = (await session.execute(l_stmt)).first()
                if lowest_res: extremes['lowest'] = dict(lowest_res._mapping)

            return extremes

    async def add_or_update_vote(self, voter_id: int, target_id: int, vote_type: int) -> Tuple[bool, str]:
        """Добавляет или обновляет голос. Реализовано через UPSERT."""
        async with self.async_session_maker() as session:
            if voter_id == target_id:
                return False, "[CMOS]: ВЫ НЕ МОЖЕТЕ ОЦЕНИВАТЬ СВОЙ СОБСТВЕННЫЙ ПРОФИЛЬ."

            stmt = pg_insert(UserRating).values(
                voter_telegram_id=voter_id,
                target_telegram_id=target_id,
                vote_type=vote_type
            )
            update_stmt = stmt.on_conflict_do_update(
                index_elements=['voter_telegram_id', 'target_telegram_id'],
                set_=dict(vote_type=vote_type, created_at=func.now())
            )

            await session.execute(update_stmt)
            await session.commit()
            return True, "[CMOS]: ✅ ВАШ ГОЛОС УЧТЕН!"

    async def get_state(self, key: str) -> Optional[str]:
        """Получает значение из таблицы состояний."""
        async with self.async_session_maker() as session:
            result = await session.execute(select(BotState.value).filter_by(key=key))
            return result.scalar_one_or_none()

    async def set_state(self, key: str, value: str):
        """Устанавливает значение в таблице состояний (UPSERT)."""
        async with self.async_session_maker() as session:
            stmt = pg_insert(BotState).values(key=key, value=value)
            update_stmt = stmt.on_conflict_do_update(
                index_elements=['key'],
                set_=dict(value=value)
            )
            await session.execute(update_stmt)
            await session.commit()

    async def select_user_for_profile_of_the_day(self) -> Optional[int]:
        """Выбирает случайного пользователя с рейтингом > 0."""
        async with self.async_session_maker() as session:
            rating_sum = func.sum(UserRating.vote_type)
            positive_users_stmt = (
                select(UserRating.target_telegram_id)
                .group_by(UserRating.target_telegram_id)
                .having(rating_sum > 0)
            )
            positive_users_result = await session.execute(positive_users_stmt)
            positive_user_ids = [row[0] for row in positive_users_result.all()]

            if not positive_user_ids:
                return None
            return random.choice(positive_user_ids)

    async def get_all_user_ids(self) -> List[int]:
        """Возвращает список всех telegram_id пользователей."""
        async with self.async_session_maker() as session:
            result = await session.execute(select(User.telegram_id))
            return [row[0] for row in result.all()]


db_manager = DatabaseManager(async_session_maker)

async def get_user_data(telegram_id: int) -> Optional[Dict]:
    return await db_manager.get_user_data(telegram_id)

async def get_user_role(telegram_id: int) -> Optional[str]:
    return await db_manager.get_user_role(telegram_id)


def escape_html(text: Optional[Any]) -> str:
    """Экранирует специальные HTML-символы в строке."""
    if not text:
        return ""
    return html.escape(str(text))


async def get_nickname_with_badge(telegram_id: int, nickname: str) -> str:
    """Возвращает никнейм с активным бейджем (если есть)."""
    try:
        from modules import badges_module
        active_badge = await badges_module.get_active_badge(telegram_id)
        if active_badge:
            badge_emoji = active_badge.get('emoji', '')
            return f"{nickname} {badge_emoji}"
        return nickname
    except Exception as e:
        logger.error(f"Ошибка получения активного бейджа для {telegram_id}: {e}")
        return nickname


async def _is_allowed(update: Update, allowed_user_id: int) -> bool:
    """Проверяет, имеет ли право пользователь взаимодействовать с сообщением."""
    query = update.callback_query
    if not query:
        return True

    user_id = query.from_user.id
    if user_id != allowed_user_id:
        await query.answer("[CMOS]: ЭТО МЕНЮ ПРЕДНАЗНАЧЕНО ДЛЯ ДРУГОГО ПОЛЬЗОВАТЕЛЯ.", show_alert=True)
        return False
    return True


class ProfileBlockManager:
    """Менеджер для динамической сборки блоков профиля из разных модулей."""

    def __init__(self):
        self.blocks: Dict[str, Dict] = {}
        self.logger = logging.getLogger(f"{__name__}.ProfileBlockManager")

    def register_block(self, block_id: str, callback: Callable[[int], Coroutine[Any, Any, Optional[dict]]], title: str, priority: int = 0):
        self.blocks[block_id] = {'callback': callback, 'title': title, 'priority': priority}
        self.logger.info(f"Зарегистрирован блок профиля: {block_id} (Приоритет: {priority})")

    def unregister_block(self, block_id: str):
        if block_id in self.blocks:
            del self.blocks[block_id]
            self.logger.info(f"Блок профиля '{block_id}' удален.")

    async def get_profile_content(self, user_id: int, is_public: bool = False) -> Tuple[List[str], List[List[InlineKeyboardButton]]]:
        if not self.blocks:
            return ["ПРОФИЛЬ НЕ НАСТРОЕН."], []

        content_parts = []
        all_buttons = []

        visibility_settings = {}
        if is_public:
            visibility_settings = await get_profile_visibility(user_id)

        public_excluded_blocks = ["registration_profile_info", "settings_profile_block"]
        sorted_blocks = sorted(self.blocks.items(), key=lambda item: item[1]['priority'], reverse=True)

        for block_id, block_info in sorted_blocks:
            if is_public:
                if block_id in public_excluded_blocks:
                    continue
                if not visibility_settings.get(block_id, True):
                    continue

            try:
                block_data = await block_info['callback'](user_id)
                if block_data and isinstance(block_data, dict) and 'content' in block_data:
                    full_block_text = f"<b>{block_info['title']}</b>\n{block_data['content']}"
                    content_parts.append(full_block_text)

                    # Кнопки, которые должны отображаться только в личном профиле, фильтруются здесь
                    if not is_public and 'buttons' in block_data and block_data['buttons']:
                        all_buttons.extend(block_data['buttons'])

            except Exception as e:
                self.logger.error(f"Ошибка при получении данных для блока профиля '{block_id}': {e}", exc_info=True)

        return content_parts, all_buttons


profile_manager = ProfileBlockManager()


async def get_quote_profile_block(telegram_id: int) -> Optional[Dict]:
    user_data = await get_user_data(telegram_id)
    if not user_data: return None
    quote = user_data.get('quote')
    nickname = escape_html(user_data.get('nickname', 'Аноним'))
    if quote:
        verbs = [
            "считает", "говорит", "думает", "полагает", "замечает", "утверждает", "заявляет", "пишет",
            "делится", "отмечает", "подчеркивает", "напоминает", "добавляет", "замечает что", "соглашается что",
            "мягко говорит что", "лаконично заявляет что", "подмечает что", "объясняет что", "уточняет что",
            "размышляет что", "размышляет над тем что", "развивает мысль что", "размышляет о том что",
            "вдумчиво говорит что", "философствует о том что", "погружается в мысль что", "анализирует что",
            "медленно осознает что", "приходит к выводу что", "сознаёт что", "вдохновенно рассуждает что",
            "искренне полагает что", "попытался понять и сказал что", "разворачивает идею что",
            "кричит", "кричит о том что", "восклицает что", "восторженно заявляет что", "радостно говорит что",
            "страстно утверждает что", "энергично подчеркивает что", "яростно говорит что", "с жаром заявляет что",
            "восторженно выкрикивает что", "искренне произносит что", "взволнованно говорит что",
            "восторженно повторяет что", "с энтузиазмом утверждает что", "радостно провозглашает что",
            "воодушевлённо говорит что", "вдохновенно заявляет что", "эмоционально подчеркивает что",
            "не может молчать и говорит что", "взрывается от желания сказать что", "говорит с чувством что",
            "сильно переживая говорит что", "почти шепчет от волнения что", "торжественно провозглашает что",
            "саркастично добавляет что", "с усмешкой говорит что", "ехидно замечает что", "иронично заявляет что",
            "с усмешкой подчеркивает что", "с ухмылкой говорит что", "подмигивает и говорит что",
            "смеясь произносит что", "подшучивает говоря что", "в шутку утверждает что", "с долей сарказма добавляет что",
            "весело говорит что", "в мемном тоне заявляет что", "с гениальным видом говорит что",
            "притворно серьёзно говорит что", "театрально произносит что", "драматично говорит что",
            "загадочно намекает что", "интригующе говорит что", "таинственно шепчет что", "мудро изрекает что",
            "со знанием дела говорит что", "уверенно провозглашает что", "безапелляционно заявляет что",
            "настойчиво утверждает что", "упорно твердит что", "решительно говорит что",
            "неожиданно говорит что", "внезапно восклицает что", "спонтанно заявляет что", "импровизируя говорит что",
            "как-то раз сказал что", "однажды заметил что", "недавно понял что", "наконец осознал что",
            "наглядно демонстрирует что", "чётко формулирует что", "ясно выражает что", "точно определяет что",
            "конкретно указывает что", "открыто признаёт что", "честно говорит что", "прямо заявляет что",
            "тихо шепчет что", "громко кричит что", "вполголоса произносит что", "беззвучно показывает что",
            "невербально демонстрирует что", "жестами объясняет что", "взглядом говорит что",
            "уверен что", "убежден что", "знает что", "понимает что", "чувствует что", "ощущает что",
            "видит что", "слышит что", "замечает что", "осознаёт что", "догадывается что"
        ]
        chosen_verb = random.choice(verbs)
        content = f"{nickname} {chosen_verb}:\n«<i>{escape_html(quote)}</i>»"
    else:
        content = "Пользователь не установил цитату."
    buttons = [[InlineKeyboardButton("✏️ Изменить", callback_data=f"profile_edit_quote_{telegram_id}")]]
    return {'content': content, 'buttons': buttons}


async def get_rating_profile_block(telegram_id: int) -> Optional[Dict]:
    rating, category, rank = await db_manager.get_user_rating_and_rank(telegram_id)
    if category == 'neutral':
        content = "Нейтральный (0)"
    else:
        category_name = "🏆 Хайп" if category == 'hype' else "📉 Антихайп"
        rank_display = f"#{rank}" if rank else "Без ранга"
        content = f"{category_name}: {rating} ({rank_display})"
    return {'content': content}

async def get_badges_profile_block(telegram_id: int) -> Optional[Dict]:
    """Формирует блок профиля для отображения и управления бейджами."""
    try:
        from modules import badges_module
    except ImportError:
        logger.warning("Модуль badges_module не найден. Блок бейджей будет отключен.")
        return None

    active_badge = await badges_module.get_active_badge(telegram_id)
    
    if active_badge:
        content = f"Активный: {active_badge['emoji']} {active_badge['display_name']}"
    else:
        content = "Активный бейдж не выбран."
        
    buttons = [[InlineKeyboardButton("🏆 Управлять бейджами", callback_data=f"profile_manage_badges_{telegram_id}")]]
    
    return {'content': content, 'buttons': buttons}

async def _display_profile(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    target_user_info: Dict, 
    is_public: bool = False,
    custom_title: Optional[str] = None
):
    """
    Отображает профиль, динамически собирая его и применяя тему оформления.
    """
    target_id = target_user_info['telegram_id']
    viewer_id = update.effective_user.id
    chat_id = update.effective_chat.id
    query = update.callback_query

    # Удаляем предыдущее сообщение, чтобы избежать конфликтов интерфейса
    if query and query.message:
        try:
            await query.message.delete()
        except (BadRequest, Forbidden) as e:
            logger.warning(f"Не удалось удалить старое сообщение при отображении профиля: {e}")

    profile_blocks, profile_buttons = await profile_manager.get_profile_content(target_id, is_public=is_public)

    nickname = escape_html(target_user_info.get('nickname', 'Пользователь')).upper()
    nickname_with_badge = await get_nickname_with_badge(target_id, nickname)
    banner_file_id = target_user_info.get('banner_file_id')

    header = f"<b>[CMOS]: "
    if custom_title:
        header += f"{escape_html(custom_title)}: {nickname_with_badge}</b>"
    else:
        profile_type = "ПУБЛИЧНЫЙ ПРОФИЛЬ" if is_public else "ВАШ ПРОФИЛЬ"
        header += f"👤 {profile_type}: {nickname_with_badge}</b>"

    profile_text = header

    if profile_blocks:
        profile_text += "\n\n" + "\n\n".join(profile_blocks)
    else:
        profile_text += "\n\nИНФОРМАЦИЯ В ПРОФИЛЕ ОТСУТСТВУЕТ."

    try:
        from themes_module import theme_manager, apply_theme_to_text
        active_theme = await theme_manager.get_user_active_theme(target_id)
        profile_text = apply_theme_to_text(profile_text, active_theme, 'profile')
    except (ImportError, AttributeError) as e:
        logger.warning(f"Не удалось применить тему к профилю: {e}")

    # Пересобираем кнопки, добавляя ID того, кто смотрит профиль, для корректной проверки прав
    final_keyboard = []
    for row in profile_buttons:
        new_row = []
        for button in row:
            # callback_data уже содержит ID владельца, добавляем ID зрителя
            new_button = InlineKeyboardButton(button.text, callback_data=f"{button.callback_data}_{viewer_id}")
            new_row.append(new_button)
        final_keyboard.append(new_row)

    if not is_public:
        banner_manage_buttons = []
        if banner_file_id:
            banner_manage_buttons.extend([
                InlineKeyboardButton("🖼️ Изменить баннер", callback_data=f"profile_banner_edit_{target_id}_{viewer_id}"),
                InlineKeyboardButton("🗑️ Удалить баннер", callback_data=f"profile_banner_delete_{target_id}_{viewer_id}")
            ])
        else:
            banner_manage_buttons.append(InlineKeyboardButton("🖼️ Добавить баннер", callback_data=f"profile_banner_edit_{target_id}_{viewer_id}"))
        if banner_manage_buttons:
             final_keyboard.insert(0, banner_manage_buttons)

    if is_public and target_id != viewer_id:
        final_keyboard.append([InlineKeyboardButton("📊 Оценить", callback_data=f"profile_rate_{target_id}_{viewer_id}")])

    final_keyboard.append([InlineKeyboardButton("❌ Закрыть", callback_data=f"profile_close_0_{viewer_id}")])
    reply_markup = InlineKeyboardMarkup(final_keyboard)

    try:
        if banner_file_id:
            await context.bot.send_photo(chat_id=chat_id, photo=banner_file_id, caption=profile_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id=chat_id, text=profile_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except BadRequest as e:
        if banner_file_id and ('file_reference_expired' in str(e).lower() or 'wrong file identifier' in str(e).lower()):
            logger.warning(f"File reference для баннера пользователя {target_id} истек. Сбрасываем баннер.")
            await db_manager.update_user_field(target_id, 'banner_file_id', None)

            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text="<b>[CMOS]:</b> ВНИМАНИЕ! ВАШ БАННЕР ПРОФИЛЯ УСТАРЕЛ И БЫЛ АВТОМАТИЧЕСКИ СБРОШЕН. ПОЖАЛУЙСТА, УСТАНОВИТЕ НОВЫЙ ЧЕРЕЗ МЕНЮ ПРОФИЛЯ.",
                    parse_mode=ParseMode.HTML
                )
            except Forbidden:
                logger.warning(f"Не удалось уведомить пользователя {target_id} о сбросе баннера (бот заблокирован).")

            await context.bot.send_message(chat_id=chat_id, text=profile_text + "\n\n<b>⚠️ [CMOS]:</b> ОШИБКА: НЕ УДАЛОСЬ ЗАГРУЗИТЬ БАННЕР. ОН БЫЛ СБРОШЕН.", reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        else:
            logger.error(f"Ошибка BadRequest при отображении профиля {target_id}: {e}")
            await context.bot.send_message(chat_id=chat_id, text="<b>[CMOS]:</b> ПРОИЗОШЛА КРИТИЧЕСКАЯ ОШИБКА ПРИ ОТОБРАЖЕНИИ ПРОФИЛЯ.", parse_mode=ParseMode.HTML)
    except Forbidden as e:
        logger.error(f"Ошибка Forbidden при отображении профиля для чата {chat_id}: {e}")


async def _update_caller_username(update: Update):
    user = update.effective_user
    if not user: return
    user_data = await get_user_data(user.id)
    if user_data and user.username != user_data.get('username'):
        await db_manager.update_user_field(user.id, 'username', user.username)
        logger.info(f"Юзернейм для пользователя {user.id} обновлен на @{user.username}.")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _update_caller_username(update)
    user_id = update.effective_user.id

    if not context.args:
        user_info = await get_user_data(user_id)
        if not user_info:
            await update.message.reply_text("<b>[CMOS]:</b> ВЫ НЕ ЗАРЕГИСТРИРОВАНЫ. ПОЖАЛУЙСТА, ИСПОЛЬЗУЙТЕ /start ДЛЯ НАЧАЛА.", parse_mode=ParseMode.HTML)
            return
        await _display_profile(update, context, user_info, is_public=False)
        return

    identifier = " ".join(context.args)
    target_user_info = await db_manager.find_user_by_identifier(identifier)
    if not target_user_info:
        await update.message.reply_text(f"<b>[CMOS]:</b> ПОЛЬЗОВАТЕЛЬ '{escape_html(identifier.upper())}' НЕ НАЙДЕН.", parse_mode=ParseMode.HTML)
        return
    await _display_profile(update, context, target_user_info, is_public=True)

async def profile_random_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает профиль случайного пользователя."""
    await _update_caller_username(update)
    random_user = await db_manager.get_random_user()
    if not random_user:
        await update.message.reply_text("<b>[CMOS]:</b> В СИСТЕМЕ ПОКА НЕТ ЗАРЕГИСТРИРОВАННЫХ ПОЛЬЗОВАТЕЛЕЙ.", parse_mode=ParseMode.HTML)
        return
    await _display_profile(update, context, random_user, is_public=True, custom_title="🎲 СЛУЧАЙНЫЙ ПРОФИЛЬ")

async def profile_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает профиль дня."""
    await _update_caller_username(update)
    daily_profile_info = await get_profile_of_the_day()
    if not daily_profile_info:
        await update.message.reply_text("<b>[CMOS]:</b> ☀️ ПРОФИЛЬ ДНЯ ЕЩЕ НЕ ВЫБРАН. ЭТО СЛУЧАЕТСЯ, ЕСЛИ НИКТО НЕ ИМЕЕТ РЕЙТИНГА ВЫШЕ 0.", parse_mode=ParseMode.HTML)
        return
    await _display_profile(update, context, daily_profile_info, is_public=True, custom_title="☀️ ПРОФИЛЬ ДНЯ")


async def trends_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _update_caller_username(update)
    text = "<b>[CMOS]:</b> 🏆 ТРЕНДЫ ПРОФИЛЕЙ\n\nВЫБЕРИТЕ КАТЕГОРИЮ ДЛЯ ПРОСМОТРА:"
    keyboard = [
        [InlineKeyboardButton("Хайп 🏆", callback_data=f"trends_show_hype_{update.effective_user.id}")],
        [InlineKeyboardButton("Антихайп 📉", callback_data=f"trends_show_antihype_{update.effective_user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.delete()
        await update.effective_chat.send_message(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def open_profile_from_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает нажатие кнопки 'Открыть профиль' на КМ-карточке."""
    query = update.callback_query
    data_parts = query.data.split('_')
    target_id = int(data_parts[2])
    allowed_user_id = int(data_parts[3])

    if not await _is_allowed(update, allowed_user_id):
        return

    await query.answer()

    target_user_info = await get_user_data(target_id)
    if not target_user_info:
        await query.answer("[CMOS]: ОШИБКА: НЕ УДАЛОСЬ НАЙТИ ЭТОГО ПОЛЬЗОВАТЕЛЯ.", show_alert=True)
        return

    is_public = target_id != allowed_user_id
    await _display_profile(update, context, target_user_info, is_public=is_public)

async def trends_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data_parts = query.data.split('_')
    allowed_user_id = int(data_parts[-1])

    if not await _is_allowed(update, allowed_user_id):
        return

    await query.answer()

    action = data_parts[2]

    if action == "menu":
        await trends_command(update, context)
        return

    lines = []
    if action == "hype":
        top_users = await db_manager.get_trends(limit=10)
        text = "<b>[CMOS]:</b> 🏆 ТРЕНДЫ ПРОФИЛЕЙ: ХАЙП\n\nТОП-10 ПОЛЬЗОВАТЕЛЕЙ С САМЫМ ВЫСОКИМ РЕЙТИНГОМ:\n\n"
        if not top_users:
            text += "<i>Пока никто не получал положительных оценок. Будьте первыми!</i>"
        else:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, user in enumerate(top_users, 1):
                nickname = escape_html(user['nickname'])
                nickname_with_badge = await get_nickname_with_badge(user['telegram_id'], nickname)
                deeplink = await generate_profile_deeplink(context, user['bot_id'])
                lines.append(f"{medals.get(i, f' {i}.')} <a href='{deeplink}'>{nickname_with_badge}</a> (Рейтинг: {user['rating']})")
            text += "\n".join(lines)

    elif action == "antihype":
        bottom_users = await db_manager.get_trends(limit=10, is_antihype=True)
        text = "<b>[CMOS]:</b> 📉 ТРЕНДЫ ПРОФИЛЕЙ: АНТИХАЙП\n\nТОП-10 ПОЛЬЗОВАТЕЛЕЙ С САМЫМ НИЗКИМ РЕЙТИНГОМ:\n\n"
        if not bottom_users:
            text += "<i>Пользователей с отрицательным рейтингом пока нет.</i>"
        else:
            for i, user in enumerate(bottom_users, 1):
                nickname = escape_html(user['nickname'])
                nickname_with_badge = await get_nickname_with_badge(user['telegram_id'], nickname)
                deeplink = await generate_profile_deeplink(context, user['bot_id'])
                lines.append(f" {i}. <a href='{deeplink}'>{nickname_with_badge}</a> (Рейтинг: {user['rating']})")
            text += "\n".join(lines)
    else:
        return

    user_role = await get_user_role(allowed_user_id)
    if user_role == 'dev':
        extremes = await db_manager.get_extreme_ratings()
        highest = extremes.get('highest')
        lowest = extremes.get('lowest')
        dev_info = "\n\n"
        if highest:
            h_nick = escape_html(highest['nickname'])
            h_link = await generate_profile_deeplink(context, highest['bot_id'])
            dev_info += f"📈 <b>Самый высокий рейтинг:</b>\n<a href='{h_link}'>{h_nick}</a> (Рейтинг: {highest['rating']})\n"
        if lowest:
            l_nick = escape_html(lowest['nickname'])
            l_link = await generate_profile_deeplink(context, lowest['bot_id'])
            dev_info += f"📉 <b>Самый низкий рейтинг:</b>\n<a href='{l_link}'>{l_nick}</a> (Рейтинг: {lowest['rating']})\n"
        if dev_info.strip(): text += dev_info

    keyboard = [[InlineKeyboardButton("◀️ Назад к выбору", callback_data=f"trends_show_menu_{allowed_user_id}")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)


async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_')
    action = data[1]
    
    allowed_user_id = int(data[-1])
    if not await _is_allowed(update, allowed_user_id):
        return

    if action == "close":
        await query.answer()
        await query.message.delete()
        return

    await query.answer()
    
    if action == "rate":
        target_id = int(data[2])
        await query.message.delete()

        text = "<b>[CMOS]:</b> КАК ВЫ ОЦЕНИВАЕТЕ ЭТОГО ПОЛЬЗОВАТЕЛЯ?"
        keyboard = [
            [InlineKeyboardButton("🔼", callback_data=f"profile_vote_up_{target_id}_{allowed_user_id}"), InlineKeyboardButton("🔽", callback_data=f"profile_vote_down_{target_id}_{allowed_user_id}")],
            [InlineKeyboardButton("◀️ Назад к профилю", callback_data=f"profile_back_{target_id}_{allowed_user_id}")]
        ]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
        return

    elif action == "vote":
        vote_type = 1 if data[2] == "up" else -1
        target_id = int(data[3])
        success, message = await db_manager.add_or_update_vote(voter_id=allowed_user_id, target_id=target_id, vote_type=vote_type)
        await query.answer(message, show_alert=True)
        target_user_info = await get_user_data(target_id)
        if target_user_info: await _display_profile(update, context, target_user_info, is_public=True)

    elif action == "back":
        target_id = int(data[2])
        target_user_info = await get_user_data(target_id)
        if target_user_info: await _display_profile(update, context, target_user_info, is_public=True)

async def back_to_self_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    allowed_user_id = int(query.data.split('_')[-1])
    if not await _is_allowed(update, allowed_user_id):
        return

    await query.answer()
    user_info = await get_user_data(allowed_user_id)
    if user_info:
        await _display_profile(update, context, user_info, is_public=False)

async def start_quote_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    # Владелец профиля, ID которого зашит в кнопку
    owner_id = int(query.data.split('_')[3])
    # Тот, кто нажал на кнопку
    user_id = query.from_user.id
    
    if user_id != owner_id:
        await query.answer("[CMOS]: ВЫ НЕ МОЖЕТЕ РЕДАКТИРОВАТЬ ЧУЖУЮ ЦИТАТУ.", show_alert=True)
        return ConversationHandler.END

    await query.answer()

    if query.message:
        await query.message.delete()

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="<b>[CMOS]:</b> ВВЕДИТЕ ВАШУ НОВУЮ ЦИТАТУ (ДО 150 СИМВОЛОВ) ИЛИ ОТПРАВЬТЕ /cancel ДЛЯ ОТМЕНЫ.",
        parse_mode=ParseMode.HTML
    )
    # Сохраняем ID пользователя для проверки в следующем шаге
    context.user_data['allowed_user_id_for_conv'] = user_id
    return AWAITING_QUOTE

async def handle_quote_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id != context.user_data.get('allowed_user_id_for_conv'):
        return AWAITING_QUOTE

    quote_text = update.message.text
    if len(quote_text) > 150:
        await update.message.reply_text("<b>[CMOS]:</b> ОШИБКА: ЦИТАТА СЛИШКОМ ДЛИННАЯ. ПОПРОБУЙТЕ ЕЩЕ РАЗ (ДО 150 СИМВОЛОВ).", parse_mode=ParseMode.HTML)
        return AWAITING_QUOTE
    success = await db_manager.update_user_field(user_id, 'quote', quote_text)
    if success: await update.message.reply_text("<b>[CMOS]:</b> ✅ ВАША ЦИТАТА УСПЕШНО ОБНОВЛЕНА!", parse_mode=ParseMode.HTML)
    else: await update.message.reply_text("<b>[CMOS]:</b> ❌ ПРОИЗОШЛА ОШИБКА ПРИ ОБНОВЛЕНИИ ЦИТАТЫ.", parse_mode=ParseMode.HTML)

    user_info = await get_user_data(user_id)
    if user_info: await _display_profile(update, context, user_info, is_public=False)
    context.user_data.pop('allowed_user_id_for_conv', None)
    return ConversationHandler.END

async def cancel_conv_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    await update.message.reply_text("<b>[CMOS]:</b> ДЕЙСТВИЕ ОТМЕНЕНО.", parse_mode=ParseMode.HTML)
    user_info = await get_user_data(user_id)
    if user_info: await _display_profile(update, context, user_info, is_public=False)
    context.user_data.pop('allowed_user_id_for_conv', None)
    context.user_data.pop('banner_file_id_to_confirm', None)
    return ConversationHandler.END


async def start_banner_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    # Владелец профиля
    owner_id = int(query.data.split('_')[3])
    # Пользователь, нажавший кнопку
    user_id = query.from_user.id
    
    if user_id != owner_id:
        await query.answer("[CMOS]: ВЫ НЕ МОЖЕТЕ РЕДАКТИРОВАТЬ ЧУЖОЙ БАННЕР.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    text = "<b>[CMOS]:</b> ОТПРАВЬТЕ МНЕ ПРЯМУЮ ССЫЛКУ НА ИЗОБРАЖЕНИЕ ИЛИ ИСПОЛЬЗУЙТЕ КНОПКУ НИЖЕ.\n\nНАПРИМЕР: `https://example.com/image.jpg`\n\nДЛЯ ОТМЕНЫ ВВЕДИТЕ /cancel."
    keyboard = [[InlineKeyboardButton("👤 Моя Аватарка", callback_data=f"profile_banner_avatar_{user_id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.delete()
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )
    context.user_data['allowed_user_id_for_conv'] = user_id
    return AWAITING_BANNER_URL

async def handle_banner_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id != context.user_data.get('allowed_user_id_for_conv'):
        return AWAITING_BANNER_URL

    url = update.message.text
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("<b>[CMOS]:</b> ЭТО НЕ ПОХОЖЕ НА ССЫЛКУ. ПОЖАЛУЙСТА, ОТПРАВЬТЕ ПРЯМУЮ ССЫЛКУ НА ИЗОБРАЖЕНИЕ.", parse_mode=ParseMode.HTML)
        return AWAITING_BANNER_URL

    keyboard = [[
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"profile_banner_confirm_{user_id}"),
        InlineKeyboardButton("❌ Отмена", callback_data=f"profile_banner_cancel_{user_id}")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        sent_message = await update.message.reply_photo(
            photo=url,
            caption="<b>[CMOS]:</b> ВОТ ТАК БУДЕТ ВЫГЛЯДЕТЬ ВАШ БАННЕР. ПОДТВЕРЖДАЕТЕ?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        file_id = sent_message.photo[-1].file_id
        context.user_data['banner_file_id_to_confirm'] = file_id

        return AWAITING_BANNER_CONFIRMATION
    except (BadRequest, Forbidden) as e:
        logger.warning(f"Не удалось загрузить изображение по ссылке {url}: {e}")
        await update.message.reply_text("<b>[CMOS]:</b> НЕ УДАЛОСЬ ЗАГРУЗИТЬ ИЗОБРАЖЕНИЕ ПО ЭТОЙ ССЫЛКЕ. УБЕДИТЕСЬ, ЧТО ЭТО ПРЯМАЯ ССЫЛКА НА ФАЙЛ (.JPG, .PNG).", parse_mode=ParseMode.HTML)
        return AWAITING_BANNER_URL

async def handle_banner_avatar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    if user_id != context.user_data.get('allowed_user_id_for_conv'):
        await query.answer("[CMOS]: ЭТО МЕНЮ ПРЕДНАЗНАЧЕНО ДЛЯ ДРУГОГО ПОЛЬЗОВАТЕЛЯ.", show_alert=True)
        return AWAITING_BANNER_URL

    await query.answer()

    try:
        photos = await context.bot.get_user_profile_photos(user_id=user_id, limit=1)
        if not photos or not photos.photos:
            await query.answer("[CMOS]: У ВАС НЕТ ПУБЛИЧНЫХ ФОТО ПРОФИЛЯ.", show_alert=True)
            return AWAITING_BANNER_URL

        file_id = photos.photos[0][-1].file_id

        keyboard = [[
            InlineKeyboardButton("✅ Подтвердить", callback_data=f"profile_banner_confirm_{user_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"profile_banner_cancel_{user_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.message.delete()

        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=file_id,
            caption="<b>[CMOS]:</b> ВОТ ТАК БУДЕТ ВЫГЛЯДЕТЬ ВАШ БАННЕР (ВАША АВАТАРКА). ПОДТВЕРЖДАЕТЕ?",
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )

        context.user_data['banner_file_id_to_confirm'] = file_id
        return AWAITING_BANNER_CONFIRMATION

    except Exception as e:
        logger.error(f"Ошибка при получении аватара пользователя {user_id}: {e}")
        await query.answer("[CMOS]: ПРОИЗОШЛА ОШИБКА ПРИ ПОЛУЧЕНИИ ВАШЕГО АВАТАРА.", show_alert=True)
        return AWAITING_BANNER_URL

async def handle_banner_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    if user_id != context.user_data.get('allowed_user_id_for_conv'):
        await query.answer("[CMOS]: ЭТО МЕНЮ ПРЕДНАЗНАЧЕНО ДЛЯ ДРУГОГО ПОЛЬЗОВАТЕЛЯ.", show_alert=True)
        return ConversationHandler.END

    await query.answer("[CMOS]: ✅ БАННЕР УСПЕШНО ОБНОВЛЕН!", show_alert=True)

    file_id_to_set = context.user_data.pop('banner_file_id_to_confirm', None)

    if not file_id_to_set:
        await query.message.delete()
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="<b>[CMOS]:</b> ПРОИЗОШЛА ОШИБКА. ПОПРОБУЙТЕ СНОВА.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

    await db_manager.update_user_field(user_id, 'banner_file_id', file_id_to_set)

    user_info = await get_user_data(user_id)
    if user_info:
        await _display_profile(update, context, user_info, is_public=False)

    context.user_data.pop('allowed_user_id_for_conv', None)
    return ConversationHandler.END

async def cancel_banner_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = query.from_user.id
    if user_id != context.user_data.get('allowed_user_id_for_conv'):
         await query.answer("[CMOS]: ЭТО МЕНЮ ПРЕДНАЗНАЧЕНО ДЛЯ ДРУГОГО ПОЛЬЗОВАТЕЛЯ.", show_alert=True)
         return ConversationHandler.END

    context.user_data.pop('banner_file_id_to_confirm', None)
    context.user_data.pop('allowed_user_id_for_conv', None)

    await query.answer("[CMOS]: УСТАНОВКА БАННЕРА ОТМЕНЕНА.")
    await query.message.delete()

    user_info = await get_user_data(user_id)
    if user_info:
        await _display_profile(update, context, user_info, is_public=False)

    return ConversationHandler.END

async def prompt_banner_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    owner_id = int(query.data.split('_')[3])
    viewer_id = int(query.data.split('_')[4])
    
    if viewer_id != owner_id:
        await query.answer("[CMOS]: ВЫ НЕ МОЖЕТЕ УДАЛИТЬ ЧУЖОЙ БАННЕР.", show_alert=True)
        return
        
    if not await _is_allowed(update, viewer_id):
        return

    await query.answer()
    await query.message.delete()

    keyboard = [[
        InlineKeyboardButton("🗑️ Да, удалить", callback_data=f"profile_banner_delete_confirm_{owner_id}_{viewer_id}"),
        InlineKeyboardButton("◀️ Нет, оставить", callback_data=f"profile_back_self_{viewer_id}")
    ]]
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="<b>[CMOS]:</b> ВЫ УВЕРЕНЫ, ЧТО ХОТИТЕ УДАЛИТЬ БАННЕР?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML
    )

async def confirm_banner_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    owner_id = int(query.data.split('_')[4])
    viewer_id = int(query.data.split('_')[5])

    if viewer_id != owner_id:
        await query.answer("[CMOS]: ВЫ НЕ МОЖЕТЕ УДАЛИТЬ ЧУЖОЙ БАННЕР.", show_alert=True)
        return

    if not await _is_allowed(update, viewer_id):
        return

    await query.answer("[CMOS]: БАННЕР УДАЛЕН.")
    await db_manager.update_user_field(owner_id, 'banner_file_id', None)

    user_info = await get_user_data(owner_id)
    if user_info:
        await _display_profile(update, context, user_info, is_public=False)

async def get_profile_of_the_day() -> Optional[Dict]:
    today_str = date.today().isoformat()
    state_json = await db_manager.get_state(PROFILE_OF_THE_DAY_KEY)
    if state_json:
        try:
            state = json.loads(state_json)
            if state.get("date") == today_str and state.get("telegram_id"):
                user_data = await get_user_data(state["telegram_id"])
                if user_data: # Убедимся, что пользователь все еще существует
                    return user_data
        except json.JSONDecodeError:
            logger.error("Ошибка декодирования JSON для профиля дня.")

    logger.info("Профиль дня не найден или устарел. Выбираем новый.")
    new_user_id = await db_manager.select_user_for_profile_of_the_day()
    if new_user_id:
        new_state = {"telegram_id": new_user_id, "date": today_str}
        await db_manager.set_state(PROFILE_OF_THE_DAY_KEY, json.dumps(new_state))
        logger.info(f"Новый профиль дня выбран: {new_user_id}")
        return await get_user_data(new_user_id)
    else:
        logger.warning("Не удалось выбрать профиль дня: нет пользователей с рейтингом > 0.")
        return None

async def broadcast_profile_of_the_day(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Запущена ежедневная задача: рассылка 'Профиля дня'.")
    daily_profile_user = await get_profile_of_the_day()
    if not daily_profile_user:
        logger.info("Рассылка отменена: профиль дня не выбран.")
        return

    profile_blocks, _ = await profile_manager.get_profile_content(daily_profile_user['telegram_id'], is_public=True)
    if not profile_blocks:
        logger.warning(f"Не удалось сгенерировать контент для профиля дня (ID: {daily_profile_user['telegram_id']}). Рассылка отменена.")
        return
    
    nickname = escape_html(daily_profile_user.get('nickname', 'Неизвестный')).upper()
    nickname_with_badge = await get_nickname_with_badge(daily_profile_user['telegram_id'], nickname)
    
    text = f"<b>[CMOS]:</b> ☀️ ПРОФИЛЬ ДНЯ: {nickname_with_badge} ☀️\n\n"
    text += "\n\n".join(profile_blocks)
    text += f"\n\nВы можете оценить его, открыв профиль: `/profile {daily_profile_user['bot_id']}`"

    banner_file_id = daily_profile_user.get('banner_file_id')

    all_users = await db_manager.get_all_user_ids()
    logger.info(f"Начинается рассылка профиля дня {len(all_users)} пользователям.")
    for user_id in all_users:
        try:
            if banner_file_id:
                await context.bot.send_photo(chat_id=user_id, photo=banner_file_id, caption=text, parse_mode=ParseMode.HTML)
            else:
                await context.bot.send_message(chat_id=user_id, text=text, parse_mode=ParseMode.HTML)
            await asyncio.sleep(0.1) # Небольшая задержка для избежания флуд-лимитов
        except Forbidden:
            logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: бот заблокирован.")
        except Exception as e:
            logger.error(f"Ошибка при рассылке пользователю {user_id}: {e}")

async def ensure_profile_of_the_day_on_startup():
    logger.info("Проверка наличия профиля дня при запуске...")
    await get_profile_of_the_day()

async def inline_profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает инлайн-запросы для поиска, отображения профилей и трендов."""
    query_text = update.inline_query.query.lower().strip()
    user_id = update.inline_query.from_user.id
    results = []
    
    # Обработка ключевых слов
    if query_text in ["random", "рандом"]:
        target_user_info = await db_manager.get_random_user()
        if target_user_info:
            title = "[CMOS]: 🎲 СЛУЧАЙНЫЙ ПРОФИЛЬ"
            description = escape_html(target_user_info.get('nickname', 'Аноним'))
    
    elif query_text in ["daily", "дейли"]:
        target_user_info = await get_profile_of_the_day()
        if target_user_info:
            title = "[CMOS]: ☀️ ПРОФИЛЬ ДНЯ"
            description = escape_html(target_user_info.get('nickname', 'Аноним'))

    elif query_text in ["hype", "хайп", "antihype", "антихайп"]:
        is_antihype = query_text in ["antihype", "антихайп"]
        title = "[CMOS]: 📉 АНТИХАЙП ТРЕНДЫ" if is_antihype else "[CMOS]: 🏆 ХАЙП ТРЕНДЫ"
        description = "Топ-10 пользователей"
        
        trends_data = await db_manager.get_trends(limit=10, is_antihype=is_antihype)
        message_text = f"<b>{title}</b>\n\n"
        if not trends_data:
            message_text += "<i>В этой категории пока пусто.</i>"
        else:
            lines = []
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, user in enumerate(trends_data, 1):
                nickname = escape_html(user['nickname'])
                medal = medals.get(i, f' {i}.') if not is_antihype else f" {i}."
                lines.append(f"{medal} {nickname} (Рейтинг: {user['rating']})")
            message_text += "\n".join(lines)
            
        results.append(InlineQueryResultArticle(
            id=str(uuid4()), title=title, description=description,
            input_message_content=InputTextMessageContent(message_text, parse_mode=ParseMode.HTML),
            thumb_url="https://i.imgur.com/bIH83E1.png"
        ))
        await update.inline_query.answer(results, cache_time=5)
        return

    # Поиск профиля по запросу или отображение своего
    else:
        if not query_text:
            target_user_info = await get_user_data(user_id)
            if target_user_info:
                title = "[CMOS]: МОЙ ПРОФИЛЬ"
                description = escape_html(target_user_info.get('nickname', 'Аноним'))
        else:
            target_user_info = await db_manager.find_user_by_identifier(query_text)
            if target_user_info:
                nickname_upper = escape_html(target_user_info.get('nickname', 'Аноним').upper())
                title = f"[CMOS]: ПРОФИЛЬ {nickname_upper}"
                description = f"Нажмите для просмотра"

    # Формирование результата для профиля
    if 'target_user_info' in locals() and target_user_info:
        profile_blocks, _ = await profile_manager.get_profile_content(target_user_info['telegram_id'], is_public=True)
        nickname = escape_html(target_user_info.get('nickname', 'Пользователь')).upper()
        nickname_with_badge = await get_nickname_with_badge(target_user_info['telegram_id'], nickname)
        header = f"<b>[CMOS]:</b> 👤 ПУБЛИЧНЫЙ ПРОФИЛЬ: {nickname_with_badge}"
        message_text = header + "\n\n" + "\n\n".join(profile_blocks)

        results.append(InlineQueryResultArticle(
            id=str(uuid4()), title=title, description=description,
            input_message_content=InputTextMessageContent(message_text, parse_mode=ParseMode.HTML),
            thumb_url="https://i.imgur.com/bIH83E1.png"
        ))
    
    # Ответ по умолчанию, если ничего не найдено
    elif not results:
         results.append(InlineQueryResultArticle(
            id="not_found", title="[CMOS]: ПРОФИЛЬ НЕ НАЙДЕН",
            description="Попробуйте другой запрос",
            input_message_content=InputTextMessageContent("<b>[CMOS]:</b> ПОЛЬЗОВАТЕЛЬ НЕ НАЙДЕН.", parse_mode=ParseMode.HTML)
        ))

    await update.inline_query.answer(results, cache_time=5)


async def badges_management_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отображает меню для выбора активного бейджа."""
    query = update.callback_query
    owner_id = int(query.data.split('_')[3])
    viewer_id = int(query.data.split('_')[4])
    
    if owner_id != viewer_id:
        await query.answer("[CMOS]: ВЫ НЕ МОЖЕТЕ УПРАВЛЯТЬ ЧУЖИМИ БЕЙДЖАМИ.", show_alert=True)
        return
        
    if not await _is_allowed(update, viewer_id):
        return
        
    await query.answer()

    try:
        from modules import badges_module
    except ImportError:
        await query.answer("[CMOS]: ОШИБКА: МОДУЛЬ БЕЙДЖЕЙ НЕ ПОДКЛЮЧЕН.", show_alert=True)
        return
        
    user_badges = await badges_module.get_user_badges(viewer_id)

    text = "<b>[CMOS]: УПРАВЛЕНИЕ БЕЙДЖАМИ</b>\n\nВыберите бейдж, который хотите отображать в профиле:"
    keyboard = []

    if not user_badges:
        text += "\n\n<i>У вас пока нет ни одного бейджа.</i>"
    else:
        for badge in user_badges:
            button = InlineKeyboardButton(
                f"{badge['emoji']} {badge['display_name']}",
                callback_data=f"profile_set_badge_{badge['id']}_{viewer_id}"
            )
            keyboard.append([button])

    keyboard.append([InlineKeyboardButton("🚫 Снять бейдж", callback_data=f"profile_set_badge_remove_{viewer_id}")])
    keyboard.append([InlineKeyboardButton("◀️ Назад к профилю", callback_data=f"profile_back_self_{viewer_id}")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.message.delete()
    except (BadRequest, Forbidden) as e:
        logger.warning(f"Не удалось удалить старое сообщение при открытии меню бейджей: {e}")
        
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

async def set_active_badge_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Устанавливает или снимает активный бейдж."""
    query = update.callback_query
    parts = query.data.split('_')
    allowed_user_id = int(parts[-1])
    badge_id_str = parts[3]

    if not await _is_allowed(update, allowed_user_id):
        return

    badge_id = None if badge_id_str == "remove" else int(badge_id_str)

    try:
        from modules import badges_module
        success, message = await badges_module.set_active_badge(allowed_user_id, badge_id)
        await query.answer(message, show_alert=True)
        # Обновляем меню управления, чтобы показать изменения
        await badges_management_callback(update, context)
    except ImportError:
        await query.answer("[CMOS]: ОШИБКА: МОДУЛЬ БЕЙДЖЕЙ НЕ ПОДКЛЮЧЕН.", show_alert=True)


def setup(core: 'BotCore') -> Tuple[List, List[str]]:
    profile_manager.register_block("profile_quote", get_quote_profile_block, "🗯️ ЦИТАТА", 90)
    profile_manager.register_block("profile_rating", get_rating_profile_block, "📊 РЕЙТИНГ", 80)
    profile_manager.register_block("profile_badges", get_badges_profile_block, "🏅 БЕЙДЖИ", 70) 

    quote_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_quote_edit, pattern=r"^profile_edit_quote_\d+_\d+$")],
        states={AWAITING_QUOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quote_input)]},
        fallbacks=[CommandHandler("cancel", cancel_conv_edit)],
        per_message=False,
    )

    banner_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_banner_edit, pattern=r"^profile_banner_edit_\d+_\d+$")],
        states={
            AWAITING_BANNER_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_banner_url),
                CallbackQueryHandler(handle_banner_avatar, pattern=r"^profile_banner_avatar_\d+$")
            ],
            AWAITING_BANNER_CONFIRMATION: [CallbackQueryHandler(handle_banner_confirm, pattern=r"^profile_banner_confirm_\d+$")]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conv_edit),
            CallbackQueryHandler(cancel_banner_edit_callback, pattern=r"^profile_banner_cancel_\d+$")
        ],
        per_message=False,
    )

    handlers = [
        quote_conv_handler,
        banner_conv_handler,
        CommandHandler("profile", profile_command),
        CommandHandler("profiler", profile_random_command),
        CommandHandler("profiled", profile_daily_command),
        CommandHandler("trends", trends_command),
        InlineQueryHandler(inline_profile_handler),
        CallbackQueryHandler(trends_callback, pattern=r"^trends_show_"),
        CallbackQueryHandler(profile_callback, pattern=r"^profile_(rate|vote|close|back)_"),
        CallbackQueryHandler(open_profile_from_card, pattern=r"^profile_open_"),
        CallbackQueryHandler(back_to_self_profile, pattern=r"^profile_back_self_"),
        CallbackQueryHandler(prompt_banner_delete, pattern=r"^profile_banner_delete_\d+_\d+$"),
        CallbackQueryHandler(confirm_banner_delete, pattern=r"^profile_banner_delete_confirm_"),
        CallbackQueryHandler(badges_management_callback, pattern=r"^profile_manage_badges_"),
        CallbackQueryHandler(set_active_badge_callback, pattern=r"^profile_set_badge_"),
    ]

    if core and hasattr(core, 'application') and core.application and core.application.job_queue:
        job_queue = core.application.job_queue
        # Запуск задачи в 12:00 по Московскому времени (UTC+3)
        job_queue.run_daily(broadcast_profile_of_the_day, time=time(hour=9, minute=0, tzinfo=pytz.UTC))
        logger.info("Ежедневная рассылка 'Профиля дня' запланирована на 9:00 UTC (12:00 MSK).")
        asyncio.create_task(ensure_profile_of_the_day_on_startup())
    else:
        logger.error("Не удалось запланировать задачу рассылки: 'job_queue' не найден или не инициализирован.")

    logger.info("Модуль профиля инициализирован.")
    return handlers, ["profile", "trends", "cancel", "profiler", "profiled"]


def cleanup():
    profile_manager.unregister_block("profile_rating")
    profile_manager.unregister_block("profile_quote")
    profile_manager.unregister_block("profile_badges")
    profile_manager.blocks.clear()
    logger.info("Модуль профиля выгружен, все блоки очищены.")