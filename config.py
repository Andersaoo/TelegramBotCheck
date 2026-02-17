# config.py
# Конфигурация сервисов для определения по комментариям Jira
# Configuration of services to be detected in Jira comments

import os
from typing import List, Dict, Union

from dotenv import load_dotenv
load_dotenv()

# Список правил для поиска сервисов в комментариях.
# Каждое правило содержит:
#   pattern: подстрока для поиска (может быть частью URL или простым текстом)
#   service: имя сервиса (если не зависит от ветки)
#   branch_based: если True, то сервис определяется по целевой ветке Merge Request
#   branch_map: словарь {ветка: имя_сервиса} для branch_based=True
#   default_service: сервис по умолчанию, если ветка не найдена в branch_map
#
# List of rules to detect services in comments.
# Each rule may contain:
#   pattern: substring to search for (can be part of URL or plain text)
#   service: service name (if not branch-dependent)
#   branch_based: if True, service is determined by MR target branch
#   branch_map: dict {branch: service_name} for branch_based=True
#   default_service: default service if branch not found in branch_map

SERVICE_PATTERNS: List[Dict[str, Union[str, bool, Dict[str, str]]]] = [
    # Правило для основного бэкенд-репозитория, где сервис зависит от ветки
    # Rule for the main backend repository where service depends on branch
    {
        "pattern": os.getenv("BACKEND_REPO_PATTERN", "gitlab.com/your-organization/backend"),
        "branch_based": True,
        "branch_map": {
            os.getenv("TARGET_BRANCH", "main"): "Cote",   # ветка, на которую указывает TARGET_BRANCH → сервис Cote
        },
        "default_service": "Django",   # если ветка не совпадает → Django
    },
    # Простые правила: подстрока → сервис
    # Simple rules: substring → service
    {"pattern": "microbackend/integrations/fundist", "service": "Fundist"},
    {"pattern": "multyprojectadmin", "service": "Multyprojectadmin"},
    {"pattern": "microbackend/integrations/digitainslots", "service": "DigitainSlots"},
    {"pattern": "microbackend/integrations/evointegrationservice", "service": "Kelt"},
    {"pattern": "microbackend/integrations/outcomeintegrationservice", "service": "Outcome"},
    {"pattern": "microbackend/integrations/pragmatic", "service": "Pragmatic"},
    {"pattern": "microbackend/integrations/softswiss", "service": "Softswiss"},
    {"pattern": "microbackend/backendbetslibrary", "service": "BettingLibrary"},
    {"pattern": "microbackend/bettingservice/", "service": "BettingService"},
    {"pattern": "microbackend/paymentsystems/", "service": "Paymentsystems"},
    {"pattern": "backend/crypto-pay/", "service": "CryptoPay"},
    {"pattern": "cps", "service": "Copi"},
    {"pattern": "fortunewheelservice/", "service": "FortuneWheelService"},
    {"pattern": "softionsport/", "service": "Softionsport"},
]