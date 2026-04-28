from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


FALLBACK_TEXT = (
    "Спасибо за вопрос. Я не нашёл точной информации в публичной базе знаний, "
    "поэтому передам обращение специалисту. Он проверит детали и поможет вам с ответом."
)

NOT_APPLICABLE_TEXT = "Сценарий B2C-консультации не применим к этому обращению."

PERSONAL_DATA_FALLBACK_TEXT = (
    "Спасибо за вопрос. Для этого запроса нужен доступ к индивидуальным данным, "
    "поэтому передам обращение специалисту. Он проверит детали и поможет вам с ответом."
)

PERSONAL_DATA_PATTERNS = [
    r"\bмо(ему|й|я|и)\b.*\bдоговор",
    r"списал[ао]сь",
    r"статус.*(обращени|договора|заявк)",
    r"персональн",
    r"измен(ить|ите).*данн",
    r"претензи",
    r"конфликт",
]

INTENT_KEYWORDS = {
    "tariff": ["тариф", "стоим", "стоит", "сколько стоит", "сколько это стоит", "комис", "оплат", "цена"],
    "onboarding": ["подключ", "оформ", "заявк", "как начать", "дистанционно", "онлайн"],
    "self_service": ["личн", "кабинет", "прилож", "опци", "истор", "настрой"],
    "rules": ["огранич", "услов", "регион", "правил", "документ", "договор"],
}


@dataclass(frozen=True)
class KnowledgeChunk:
    title: str
    text: str
    tags: Tuple[str, ...]


PUBLIC_KB: List[KnowledgeChunk] = [
    KnowledgeChunk(
        title="Тарифы и стоимость",
        text=(
            "Для физических лиц доступны базовый, расширенный и премиум тарифы. "
            "Стоимость зависит от выбранного тарифа, набора услуг и региона обслуживания. "
            "Актуальные условия и комиссии публикуются в правилах тарификации."
        ),
        tags=("тариф", "стоимость", "стоит", "комиссия", "оплата", "цена", "сколько стоит"),
    ),
    KnowledgeChunk(
        title="Подключение и оформление",
        text=(
            "Подключить услугу можно онлайн: выберите продукт, заполните заявку и подтвердите данные. "
            "Обычно требуется документ, удостоверяющий личность. "
            "После отправки заявки статус можно проверять в личном кабинете, если функция доступна для продукта."
        ),
        tags=("подключ", "оформ", "заявк", "онлайн", "паспорт", "начать"),
    ),
    KnowledgeChunk(
        title="Личный кабинет и приложение",
        text=(
            "В личном кабинете и мобильном приложении можно смотреть тариф, подключенные опции, "
            "историю операций и управлять услугами. "
            "Приложение доступно в официальных магазинах приложений."
        ),
        tags=("личн", "кабинет", "приложен", "опци", "истори", "настрой"),
    ),
    KnowledgeChunk(
        title="Ограничения и публичные условия",
        text=(
            "Перед подключением рекомендуется проверить публичные условия обслуживания: "
            "региональные ограничения, требования к клиенту, доступность дистанционного оформления и правила использования услуги."
        ),
        tags=("огранич", "услов", "регион", "правила", "документ", "требован"),
    ),
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _is_applicable(payload: Dict[str, Any]) -> bool:
    return payload.get("client_type") == "B2C" and payload.get("topic") == "consultation"


def _needs_human(question_text: str) -> bool:
    q = _normalize(question_text)
    return any(re.search(pattern, q) for pattern in PERSONAL_DATA_PATTERNS)


def _extract_query(payload: Dict[str, Any]) -> Tuple[str, str]:
    question_text = str(payload.get("question_text", ""))
    history = payload.get("dialog_context", {}).get("messages_history", [])
    history_text = " ".join(msg.get("text", "") for msg in history if isinstance(msg, dict))
    return _normalize(question_text), _normalize(history_text)


def _detect_intents(text: str) -> List[str]:
    intents: List[str] = []
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            intents.append(intent)
    return intents


def _score_chunk(question_text: str, history_text: str, chunk: KnowledgeChunk) -> int:
    score = 0

    # Приоритет: текущий вопрос важнее истории.
    for tag in chunk.tags:
        if tag in question_text:
            score += 4
        if tag in history_text:
            score += 1

    # Намерения из текущего вопроса дают дополнительный вес.
    question_intents = _detect_intents(question_text)
    if "tariff" in question_intents and chunk.title == "Тарифы и стоимость":
        score += 5
    if "onboarding" in question_intents and chunk.title == "Подключение и оформление":
        score += 5
    if "self_service" in question_intents and chunk.title == "Личный кабинет и приложение":
        score += 5
    if "rules" in question_intents and chunk.title == "Ограничения и публичные условия":
        score += 5

    # Лёгкий фуллтекст-скоринг.
    chunk_text = chunk.text.lower()
    for word in set((question_text + " " + history_text).split()):
        if len(word) > 4 and word in chunk_text:
            score += 1

    return score


def _friendly_answer(question: str, chunk: KnowledgeChunk) -> str:
    return (
        f"Спасибо за вопрос. {chunk.text} "
        "Если хотите, могу подсказать следующий шаг именно для вашего случая "
        f"(например, как найти нужный раздел по теме: «{question.strip()}»)."
    )


def process_b2c_consultation(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not _is_applicable(payload):
        return {"answer_text": NOT_APPLICABLE_TEXT, "answer_found": False}

    question_text = str(payload.get("question_text", "")).strip()
    if not question_text:
        return {"answer_text": FALLBACK_TEXT, "answer_found": False}

    if _needs_human(question_text):
        return {"answer_text": PERSONAL_DATA_FALLBACK_TEXT, "answer_found": False}

    normalized_question, normalized_history = _extract_query(payload)
    ranked = sorted(
        PUBLIC_KB,
        key=lambda chunk: _score_chunk(normalized_question, normalized_history, chunk),
        reverse=True,
    )
    best = ranked[0]
    best_score = _score_chunk(normalized_question, normalized_history, best)

    if best_score < 3:
        return {"answer_text": FALLBACK_TEXT, "answer_found": False}

    return {"answer_text": _friendly_answer(question_text, best), "answer_found": True}


if __name__ == "__main__":
    example = {
        "question_text": "Какие тарифы доступны для физических лиц?",
        "dialog_context": {"messages_history": []},
        "client_type": "B2C",
        "topic": "consultation",
    }
    print(process_b2c_consultation(example))
