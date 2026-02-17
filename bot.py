# bot.py
# Основной файл бота
# Main bot file

import asyncio
import os
import re
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from dotenv import load_dotenv

from config import SERVICE_PATTERNS

# Загружаем переменные окружения из .env
load_dotenv()

# Конфигурация из переменных окружения
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "BACK")
GITLAB_PRIVATE_TOKEN = os.getenv("GITLAB_PRIVATE_TOKEN")
TARGET_BRANCH = os.getenv("TARGET_BRANCH", "main")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверка обязательных переменных
required_vars = {
    "JIRA_URL": JIRA_URL,
    "JIRA_EMAIL": JIRA_EMAIL,
    "JIRA_API_TOKEN": JIRA_API_TOKEN,
    "GITLAB_PRIVATE_TOKEN": GITLAB_PRIVATE_TOKEN,
    "BOT_TOKEN": BOT_TOKEN,
}
missing = [name for name, value in required_vars.items() if not value]
if missing:
    raise ValueError(f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}")

# Jira API
API_URL = f"{JIRA_URL.rstrip('/')}/rest/api/3"
JIRA_AUTH = aiohttp.BasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

# Хранилище данных пользователей
user_data: Dict[int, Dict[str, Any]] = {}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Создаёт основную клавиатуру с кнопками команд на русском."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/start"), KeyboardButton(text="/set_interval")],
            [KeyboardButton(text="/check"), KeyboardButton(text="/current")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите команду"
    )
    return keyboard


async def fetch_jira_issues(release_name: str) -> List[Dict]:
    """Асинхронно получает задачи Jira для указанного релиза."""
    url = f"{API_URL}/search/jql"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jql": f'fixVersion = "{release_name}"',
        "maxResults": 100,
        "fields": ["key", "summary", "status", "customfield_11087", "comment"]
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload, headers=headers, auth=JIRA_AUTH, timeout=10) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("issues", [])
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return []


async def check_mr_target_branch(mr_url: str) -> bool:
    """Проверяет, ведёт ли MR в целевую ветку (TARGET_BRANCH)."""
    headers = {"PRIVATE-TOKEN": GITLAB_PRIVATE_TOKEN}
    pattern = r'https://gitlab\.com/(.+?)/-/merge_requests/(\d+)'
    match = re.search(pattern, mr_url)

    if not match:
        return False

    project_path = match.group(1)
    mr_id = match.group(2)
    encoded_project = urllib.parse.quote_plus(project_path)
    api_url = f"https://gitlab.com/api/v4/projects/{encoded_project}/merge_requests/{mr_id}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return False
                data = await resp.json()
                return data.get("target_branch") == TARGET_BRANCH
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False


def extract_text_from_comment(comment_body: Any) -> str:
    """Извлекает чистый текст из комментария Jira в формате ADF."""
    if isinstance(comment_body, str):
        return comment_body

    if not isinstance(comment_body, dict):
        return ""

    text_parts = []
    content = comment_body.get('content', [])
    for item in content:
        if isinstance(item, dict):
            for sub_item in item.get('content', []):
                if isinstance(sub_item, dict) and 'text' in sub_item:
                    text_parts.append(sub_item['text'])
    return ' '.join(text_parts)


async def get_services_from_issue(issue: Dict) -> List[str]:
    """Анализирует комментарии задачи и возвращает список сервисов для деплоя."""
    services = []
    comments = issue.get("fields", {}).get("comment", {}).get("comments", [])

    for comment in comments:
        body = comment.get('body', '')
        text = extract_text_from_comment(body).lower()

        for rule in SERVICE_PATTERNS:
            pattern = rule["pattern"].lower()
            if pattern not in text:
                continue

            if rule.get("branch_based"):
                urls = re.findall(r'(https?://[^\s]+)', text)
                for url in urls:
                    if pattern in url:
                        is_target = await check_mr_target_branch(url)
                        if is_target:
                            service_name = rule["branch_map"].get(TARGET_BRANCH, rule.get("default_service", "Unknown"))
                        else:
                            service_name = rule.get("default_service", "Unknown")
                        if service_name not in services:
                            services.append(service_name)
            else:
                service_name = rule["service"]
                if service_name not in services:
                    services.append(service_name)

    return services


async def show_release_details(chat_id: int, release_name: str, show_review_only: bool = False):
    """Отображает детальную информацию о релизе в Telegram."""
    issues = await fetch_jira_issues(release_name)

    if not issues:
        await bot.send_message(chat_id, f"❌ В релизе '{release_name}' нет задач")
        return

    if show_review_only:
        review_issues = []
        for issue in issues:
            status = issue.get("fields", {}).get("status", {}).get("name", "").lower()
            if "review" in status or "ревью" in status:
                review_issues.append(issue)

        if not review_issues:
            await bot.send_message(chat_id, f"📭 В релизе '{release_name}' нет задач в статусе Review")
            return

        issues = review_issues
        title_suffix = " (ТОЛЬКО задачи в Review)"
    else:
        title_suffix = ""

    # Группировка по сервисам
    result: Dict[str, List[Dict]] = {}
    issue_service_map: Dict[str, str] = {}

    for issue in issues:
        services = await get_services_from_issue(issue)
        for service in services:
            if service not in result:
                result[service] = []
            workratio = issue.get("fields", {}).get('customfield_11087')
            workratio_str = "None" if workratio is None else str(workratio)
            result[service].append({
                'key': issue["key"],
                'name': issue["fields"]['summary'],
                'workratio': workratio_str,
                'status': issue.get("fields", {}).get("status", {}).get("name", "Неизвестно")
            })
            issue_service_map[issue["key"]] = service

    report_lines = []
    for service, issues_list in result.items():
        report_lines.append(f"{service}")
        for issue_data in issues_list:
            status_icon = "👁‍🗨" if "review" in issue_data['status'].lower() or "ревью" in issue_data['status'].lower() else "📋"
            report_lines.append(
                f"{status_icon} {issue_data['key']} - {issue_data['name']} - Попыток QA: {issue_data['workratio']}"
            )
        report_lines.append("")

    if not show_review_only:
        report_lines.append("БОЛЬШОЕ КОЛИЧЕСТВО РЕВОРКОВ")
        for issue in issues:
            try:
                workratio = issue.get("fields", {}).get('customfield_11087', 0)
                if workratio and float(workratio) > 3:
                    report_lines.append(
                        f"⚠️ {issue['key']} - {issue['fields']['summary']} - Попыток QA: {workratio}"
                    )
            except (ValueError, TypeError):
                continue

        report_lines.append("")
        report_lines.append("─" * 40)
        report_lines.append("")

        deploy_tasks = []
        for issue in issues:
            if issue.get("fields", {}).get("status", {}).get("name") == 'Deploy':
                if issue['key'] in issue_service_map:
                    deploy_tasks.append(f"{issue['key']} перевести в деплой сервис {issue_service_map[issue['key']]}")

        if deploy_tasks:
            report_lines.extend(deploy_tasks)
            report_lines.append("")

    full_report = f"📊 Релиз: {release_name}{title_suffix}\nНайдено задач: {len(issues)}\n\n" + "\n".join(report_lines)

    # Разбивка на части
    message_parts = []
    current_part = ""
    for line in full_report.split('\n'):
        if len(current_part) + len(line) + 1 > 4000:
            message_parts.append(current_part)
            current_part = line + '\n'
        else:
            current_part += line + '\n'
    if current_part:
        message_parts.append(current_part)

    for part in message_parts:
        await bot.send_message(chat_id, f"```\n{part}\n```", parse_mode='Markdown')
        await asyncio.sleep(0.5)

    # Инлайн-кнопки
    keyboard = InlineKeyboardBuilder()
    if show_review_only:
        keyboard.button(text="📋 Показать все задачи релиза", callback_data=f"rel_{release_name}")
        keyboard.button(text="🔗 Отправить ссылки на Review задачи", callback_data=f"links_{release_name}")
    else:
        keyboard.button(text="👁‍🗨 Показать задачи в Review", callback_data=f"review_{release_name}")
        keyboard.button(text="🔗 Отправить ссылки на Review задачи", callback_data=f"links_{release_name}")
    keyboard.button(text="← Назад к списку релизов", callback_data="back_to_list")
    keyboard.adjust(1)

    await bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard.as_markup())


async def send_release_links(chat_id: int, release_name: str):
    """Отправляет HTML-ссылки на задачи в статусе Review."""
    issues = await fetch_jira_issues(release_name)

    if not issues:
        await bot.send_message(chat_id, f"❌ В релизе '{release_name}' нет задач")
        return

    review_issues = []
    for issue in issues:
        status = issue.get("fields", {}).get("status", {}).get("name", "").lower()
        if "review" in status or "ревью" in status:
            review_issues.append(issue)

    if not review_issues:
        await bot.send_message(chat_id, f"📭 В релизе '{release_name}' нет задач в статусе Review")
        return

    message = f"🔗 <b>Ссылки на задачи в статусе Review (Релиз: {release_name})</b>\n\n"
    for issue in review_issues:
        issue_key = issue["key"]
        summary = issue.get("fields", {}).get("summary", "Без названия")
        issue_url = f"{JIRA_URL}/browse/{issue_key}"
        message += f"• <a href='{issue_url}'>{issue_key}</a> - {summary}\n"

    message += f"\n📊 Всего задач в Review: {len(review_issues)}"

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="👁‍🗨 Подробный отчёт", callback_data=f"review_{release_name}")
    keyboard.button(text="📋 Все задачи релиза", callback_data=f"rel_{release_name}")
    keyboard.button(text="← Назад к списку релизов", callback_data="back_to_list")
    keyboard.adjust(1)

    await bot.send_message(chat_id, message, parse_mode='HTML', disable_web_page_preview=True,
                           reply_markup=keyboard.as_markup())


async def fetch_project_versions() -> List[Dict]:
    """Получает список версий проекта из Jira."""
    url = f"{API_URL}/project/{PROJECT_KEY}/versions"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, auth=JIRA_AUTH, timeout=10) as resp:
                if resp.status != 200:
                    return []
                return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return []


async def send_releases_list(chat_id: int, from_auto_report: bool = False):
    """Отправляет список доступных релизов с задачами."""
    versions = await fetch_project_versions()

    if not versions:
        await bot.send_message(chat_id, "❌ Ошибка при получении списка релизов")
        return

    keyboard = InlineKeyboardBuilder()
    for version in versions[:20]:
        release_name = version.get('name', 'Без названия')
        issues = await fetch_jira_issues(release_name)
        count = len(issues)
        if count > 0:
            review_count = sum(1 for i in issues if "review" in i.get("fields", {}).get("status", {}).get("name", "").lower())
            button_text = f"{release_name} ({count} задач"
            if review_count > 0:
                button_text += f", {review_count} в ревью"
            button_text += ")"
            keyboard.button(text=button_text, callback_data=f"rel_{release_name}")

    keyboard.adjust(1)

    if keyboard.buttons:
        await bot.send_message(chat_id, "📋 Выберите релиз для просмотра задач:", reply_markup=keyboard.as_markup())
    else:
        await bot.send_message(chat_id, "❌ Во всех релизах пока нет задач")


# --- Обработчики команд ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id] = {'chat_id': message.chat.id}
    text = """
🤖 Бот для проверки релизов Jira

<b>Команды:</b>
/check - Показать список релизов
/set_interval - Настроить автоматическую проверку
/current - Текущие настройки

<b>Используйте кнопки внизу для быстрого доступа к командам!</b>
    """
    await message.answer(text, parse_mode='HTML', reply_markup=get_main_keyboard())


@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id] = {'chat_id': message.chat.id}
    await message.answer("🔍 Загружаю список релизов...", reply_markup=get_main_keyboard())
    await send_releases_list(message.chat.id)


@dp.message(Command("set_interval"))
async def cmd_set_interval(message: types.Message):
    user_id = message.from_user.id
    user_data[user_id] = {'chat_id': message.chat.id}
    keyboard = InlineKeyboardBuilder()
    buttons = [("10 мин", 10), ("30 мин", 30), ("60 мин", 60), ("Выключить", 0)]
    for text, interval in buttons:
        keyboard.button(text=text, callback_data=f"int_{interval}")
    keyboard.adjust(2)
    await message.answer("Выберите интервал автоматической проверки:", reply_markup=keyboard.as_markup())


@dp.callback_query(F.data.startswith("int_"))
async def process_interval(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    interval = int(callback.data.split("_")[1])

    user_data[user_id]['interval'] = interval

    if 'job_id' in user_data[user_id]:
        try:
            scheduler.remove_job(user_data[user_id]['job_id'])
        except:
            pass

    if interval > 0:
        job = scheduler.add_job(
            send_auto_report,
            IntervalTrigger(minutes=interval),
            args=[user_id],
            id=f"user_{user_id}",
            replace_existing=True
        )
        user_data[user_id]['job_id'] = job.id
        await callback.message.edit_text(f"✅ Автопроверка установлена: каждые {interval} минут")
    else:
        user_data[user_id]['job_id'] = None
        await callback.message.edit_text("✅ Автоматическая проверка выключена")

    await callback.answer()


@dp.callback_query(F.data.startswith("rel_"))
async def process_release(callback: types.CallbackQuery):
    release_name = callback.data.split("_", 1)[1]
    await callback.message.edit_text(f"🔍 Проверяю релиз '{release_name}'...")
    await show_release_details(callback.message.chat.id, release_name, show_review_only=False)
    await callback.answer()


@dp.callback_query(F.data.startswith("review_"))
async def process_review(callback: types.CallbackQuery):
    release_name = callback.data.split("_", 1)[1]
    await callback.message.edit_text(f"👁‍🗨 Ищу задачи в Review для релиза '{release_name}'...")
    await show_release_details(callback.message.chat.id, release_name, show_review_only=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("links_"))
async def process_links(callback: types.CallbackQuery):
    release_name = callback.data.split("_", 1)[1]
    await callback.message.edit_text(f"🔗 Формирую ссылки для релиза '{release_name}'...")
    await send_release_links(callback.message.chat.id, release_name)
    await callback.answer()


@dp.callback_query(F.data == "back_to_list")
async def back_to_list(callback: types.CallbackQuery):
    await callback.message.delete()
    await send_releases_list(callback.message.chat.id)
    await callback.answer()


@dp.message(Command("current"))
async def cmd_current(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_data:
        await message.answer("Используйте /start")
        return
    interval = user_data[user_id].get('interval', 'Не установлен')
    text = f"<b>Текущие настройки:</b>\nИнтервал проверки: {interval if interval else 'Выключено'} минут"
    await message.answer(text, parse_mode='HTML', reply_markup=get_main_keyboard())


# --- Автоматический отчёт ---

async def send_auto_report(user_id: int):
    if user_id not in user_data:
        return
    chat_id = user_data[user_id].get('chat_id')
    if not chat_id:
        return

    versions = await fetch_project_versions()
    if not versions:
        return

    versions.sort(key=lambda x: x.get('startDate', ''), reverse=True)

    message = "<b>📊 АВТОМАТИЧЕСКАЯ ПРОВЕРКА</b>\n\n"
    total_tasks = 0
    total_review = 0
    shown_releases = 0

    for version in versions[:10]:
        release_name = version.get('name', 'Без названия')
        issues = await fetch_jira_issues(release_name)
        if issues:
            total_tasks += len(issues)
            shown_releases += 1
            review_count = sum(1 for i in issues if "review" in i.get("fields", {}).get("status", {}).get("name", "").lower())
            total_review += review_count

            high_rework = 0
            for issue in issues:
                try:
                    workratio = issue.get("fields", {}).get('customfield_11087', 0)
                    if workratio and float(workratio) > 3:
                        high_rework += 1
                except:
                    continue

            message += f"<b>{release_name}</b>\n"
            message += f"📋 {len(issues)} задач"
            if review_count > 0:
                message += f" | 👁‍🗨 {review_count} в ревью"
            if high_rework > 0:
                message += f" | ⚠️ {high_rework} с реворками"
            message += "\n\n"

    if total_tasks > 0:
        message += f"<b>📈 ИТОГО:</b> {shown_releases} релизов, {total_tasks} задач"
        if total_review > 0:
            message += f", {total_review} в ревью"
        message += f"\n<b>⏰ Время:</b> {datetime.now().strftime('%H:%M %d.%m.%Y')}"

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📋 Показать все релизы", callback_data="show_all_releases")
        keyboard.button(text="👁‍🗨 Задачи в Review", callback_data="show_review_summary")
        keyboard.adjust(1)

        await bot.send_message(chat_id, message, parse_mode='HTML', reply_markup=keyboard.as_markup())


@dp.callback_query(F.data == "show_all_releases")
async def show_all_releases(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 Загружаю список релизов...")
    await send_releases_list(callback.message.chat.id, from_auto_report=True)
    await callback.answer()


@dp.callback_query(F.data == "show_review_summary")
async def show_review_summary(callback: types.CallbackQuery):
    versions = await fetch_project_versions()
    if not versions:
        await callback.message.edit_text("❌ Ошибка при получении данных")
        return

    versions.sort(key=lambda x: x.get('startDate', ''), reverse=True)

    message = "<b>👁‍🗨 ЗАДАЧИ В СТАТУСЕ REVIEW</b>\n\n"
    total_review = 0

    for version in versions[:10]:
        release_name = version.get('name', 'Без названия')
        issues = await fetch_jira_issues(release_name)
        if issues:
            review_issues = [i for i in issues if "review" in i.get("fields", {}).get("status", {}).get("name", "").lower()]
            if review_issues:
                total_review += len(review_issues)
                message += f"<b>{release_name}</b> - {len(review_issues)} задач\n"

    if total_review > 0:
        message += f"\n<b>📊 Всего задач в Review:</b> {total_review}"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📋 Показать все релизы", callback_data="show_all_releases")
        keyboard.button(text="← Назад", callback_data="back_to_auto_report")
        keyboard.adjust(1)
        await callback.message.edit_text(message, parse_mode='HTML', reply_markup=keyboard.as_markup())
    else:
        await callback.message.edit_text("📭 Нет задач в статусе Review")


@dp.callback_query(F.data == "back_to_auto_report")
async def back_to_auto_report(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()


# --- Запуск ---

async def main():
    scheduler.start()
    print("🤖 Бот запущен")
    print(f"🔗 Jira URL: {JIRA_URL}")
    print(f"📁 Проект: {PROJECT_KEY}")

    # Тестовый запрос
    try:
        issues = await fetch_jira_issues("1.10.2")
        print(f"✅ Тест подключения: релиз '1.10.2' содержит {len(issues)} задач")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())