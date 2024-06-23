import json
import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import (
    APIRequestError,
    InvalidAPIResponseError,
    MissingTokensError,
    UnknownHomeworkStatusError,
)

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}
PAYLOAD = {"from_date": 0}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

TEXT = "Hi, practicum"

logging.basicConfig(
    level=logging.DEBUG,
    encoding="utf-8",
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logging.StreamHandler(sys.stdout)
logger = logging.getLogger(__name__)


def check_tokens():
    """Проверяет наличие необходимых переменных окружения."""
    tokens = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
    missing_tokens = [name for name in tokens if not globals()[name]]
    if missing_tokens:
        missing_tokens_message = ", ".join(missing_tokens)
        message = (
            "Отсутствует обязательная переменная окружения: "
            f"{missing_tokens_message}."
        )
        logger.critical(message)
        raise MissingTokensError(message)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.info("Начало отправки сообщения.")
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Бот отправил сообщение "%s".', message)
    except Exception as error:
        logging.error("Ошибка отправки сообщения: %s.", error)


def get_api_answer(timestamp):
    """Делает запрос к API."""
    params = {"from_date": timestamp}
    logging.info("Производим запрос к %s с параметрами %s.", ENDPOINT, params)
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params=params, timeout=10)
    except requests.RequestException as error:
        raise APIRequestError(
            f"Ошибка запроса к {ENDPOINT} c params={params}."
        ) from error

    if response.status_code != HTTPStatus.OK:
        logging.error(
            "Эндпоинт %s недоступен, статус код: %s",
            ENDPOINT, response.status_code
        )
        raise APIRequestError(f"Эндпоинт - {ENDPOINT} недоступен.")

    logging.info("Запрос к %s с параметрами %s успешен!", ENDPOINT, params)

    try:
        response = response.json()
    except json.JSONDecodeError as error:
        logging.error('API response is not in format', error)

    return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    logging.info("Проверка ответа началась.")
    if not isinstance(response, dict):
        raise TypeError("Ответ не является словарем.")
    if "homeworks" not in response:
        raise InvalidAPIResponseError(
            'Отсутствует ожидаемый ключ "homeworks" в ответе API.'
        )
    if "current_date" not in response:
        raise InvalidAPIResponseError(
            'Отсутствует ожидаемый ключ "current_date" в ответе API.'
        )
    homeworks = response.get("homeworks")
    if not isinstance(homeworks, list):
        raise TypeError("Значение ключа homeworks не является списком.")
    if not homeworks:
        logging.info("Список домашних работ пуст.")
    return homeworks


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    if "homework_name" not in homework or "status" not in homework:
        logging.error(
            "Отсутствуют ключи homework_name или status в ответе API")
        raise InvalidAPIResponseError(
            "Отсутствуют ключи homework_name или status в ответе API"
        )
    homework_name = homework["homework_name"]
    homework_status = homework["status"]
    if homework_status not in HOMEWORK_VERDICTS:
        logging.error("Неизвестный статус домашней работы: %s",
                      homework_status)
        raise UnknownHomeworkStatusError(
            f"Неизвестный статус домашней работы: {homework_status}"
        )
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telebot.TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    send_message(bot, TEXT)

    last_error_message = None

    try:
        while True:
            try:
                response = get_api_answer(timestamp)
                if not response:
                    logging.error("Ошибка запроса к эндпоинту: %s.")

                homeworks = check_response(response)
                if homeworks:
                    message = parse_status(homeworks[0])
                    send_message(bot, message)
                else:
                    logging.debug("Отсутствие новых статусов в ответе API.")
                timestamp = response.get("current_date", timestamp)
            except Exception as error:
                message = f"Сбой в работе программы: {error}."
                logging.error(message, exc_info=True)
                if last_error_message != message:
                    send_message(bot, message)
                    last_error_message = message
            finally:
                time.sleep(RETRY_PERIOD)
    except KeyboardInterrupt:
        logging.info("Программа остановлена пользователем.")


if __name__ == "__main__":
    main()
