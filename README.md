ЭТот бот родился из лени и желания автоматизировать рутину. Если ваша команда сидит в Jira и GitLab, а перед каждым релизом приходится вручную перебирать задачи, смотреть статусы, реворки и затронутые сервисы – добро пожаловать в клуб. Теперь всё это можно делать прямо в Telegram.

🤔 Что он умеет?
Показывать список всех активных релизов и количество задач в каждом.

Выдавать подробный отчёт по выбранному релизу: группировка по микросервисам (Django, Fundist, BettingService и ещё штук 10), количество «попыток QA» (наши реворки).

Фильтровать задачи в статусе Review – чтобы сразу видеть, что готово к проверке.

Присылать прямые ссылки на эти задачи – не надо лазить по Jira.

Слать автоматические сводки по расписанию (интервал настраивается).

🛠 Как это работает под капотом
Бот написан на Python, использует aiogram для общения с Telegram, requests для запросов к API Jira и GitLab, и apscheduler для авторассылок. Самое сложное было вытаскивать из комментариев Jira ссылки на мерж-реквесты и понимать, к какому сервису они относятся. Но мы справились.

📦 Установка и запуск
Клонируй репозиторий:

bash
git clone https://github.com/Andersaoo/TelegramBotCheck.git
cd TelegramBotCheck
Создай и активируй виртуальное окружение (по желанию, но лучше):

bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
Установи зависимости:

bash
pip install -r requirements.txt
Скопируй файл .env.example в .env и заполни своими данными:

ini
BOT_TOKEN=токен_твоего_бота_от_BotFather

JIRA_URL=https://твой-домен.atlassian.net

JIRA_EMAIL=твой-email@example.com

JIRA_API_TOKEN=токен_Jira_API

GITLAB_PRIVATE_TOKEN=токен_GitLab

TARGET_BRANCH=cote-divoire   # главная ветка, куда идут мержи

Запусти бота:

bash
python bot.py
ГОтово! Теперь можно писать боту в Telegram и пользоваться.

🔗 Ссылки
Репозиторий: https://github.com/Andersaoo/TelegramBotCheck

Если найдутся баги или идеи – велкам в Issues или PR.

Пользуйтесь, автоматизируйте, не стесняйтесь! 😉

This bot was born out of laziness and a desire to automate routine tasks. If your team uses Jira and GitLab, and before each release you have to manually sort through issues, check statuses, reworks, and affected services—welcome to the club. Now you can do all this right in Telegram.

🤔 What can it do?
Show a list of all active releases and the number of issues in each.

Generate a detailed report on the selected release: grouped by microservices (Django, Fundist, BettingService, and about 10 more), the number of "QA attempts" (our reworks).

Filter issues in the "Review" status to immediately see what's ready for review.

Send direct links to these issues—no need to navigate Jira.

Send automatic scheduled summaries (interval is configurable).

🛠 How it works under the hood
The bot is written in Python and uses aiogram to communicate with Telegram, requests to query the Jira and GitLab APIs, and apscheduler for automated dispatches. The hardest part was extracting merge request links from Jira comments and understanding which service they belong to. But we managed.

📦 Installation and Launch
Clone the repository:

bash
git clone https://github.com/Andersaoo/TelegramBotCheck.git
cd TelegramBotCheck
Create and activate a virtual environment (optional, but preferred):

bash
python -m venv venv
source venv/bin/activate # for Linux/Mac
venv\Scripts\activate # for Windows
Install dependencies:

bash
pip install -r requirements.txt
Copy the .env.example file to .env and fill it with your own Data:

ini
BOT_TOKEN=your_bot_token_from_BotFather

JIRA_URL=https://your-domain.atlassian.net

JIRA_EMAIL=your-email@example.com

JIRA_API_TOKEN=Jira_API_token

GITLAB_PRIVATE_TOKEN=GitLab_token

TARGET_BRANCH=cote-divoire # master branch where merges are sent

Run the bot:

bash
python bot.py
DONE! Now you can message the bot in Telegram and use it.

🔗 Links
Repository: https://github.com/Andersaoo/TelegramBotCheck

If you find any bugs or suggestions, welcome to Issues or PRs.

Use it, automate it, don't be shy! 😉