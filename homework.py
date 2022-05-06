import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('practicum')
TELEGRAM_TOKEN = os.getenv('telegram')
TELEGRAM_CHAT_ID = os.getenv('chat')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)


def send_message(bot, message):
    """Отправляет сообщение в Telegram об изменении статуса домашки."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(f'Сообщение отправлено в Telegram {message}.')
    except Exception:
        logger.error('Сбой при отправке сообщения в Telegram.')


def get_api_answer(current_timestamp):
    """Получаем данные по API от Яндекс.Практикума о статусе домашки."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        logger.error('Ответ по API не получен')
        raise Exception('Ответ по API не получен')
    response = response.json()
    return response


def check_response(response):
    """Проверем соответствует ли ответ сервера ожидаемым данным."""
    if not isinstance(response, dict):
        logger.error('Формат ответа API отличается от ожидаемого')
        raise TypeError('Формат ответа API отличается от ожидаемого')
    homework = response.get('homeworks')
    if not isinstance(homework, list):
        logger.error('Тип значения домашки отличается от ожидаемого')
        raise TypeError('Тип значения домашки отличается от ожидаемого')
    return homework


def parse_status(homework):
    """Получаем текущий статус проверки задания."""
    if 'homework_name' not in homework:
        logger.error('Ответ API не содержит ключ \'homework_name\'')
        raise KeyError('Ответ API не содержит ключ \'homework_name\'')
    if 'status' not in homework:
        logger.error('Ответ API не содержит ключ \'status\'')
        raise KeyError('Ответ API не содержит ключ \'status\'')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяем доступность токенов и chat_id."""
    if (PRACTICUM_TOKEN is not None or TELEGRAM_TOKEN is not None
            or TELEGRAM_CHAT_ID is not None):
        return True
    else:
        return False


def main():
    """Основная логика работы бота."""
    if check_tokens() is not True:
        logger.critical('Отсутствует токены для запуска программы')
        raise ValueError('Отсутствует токены для запуска программы')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('Нет новых статусов проверки домашки.')
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
            logger.error(error_message)
            if error_message != last_error:
                send_message(bot, error_message)
                last_error = error_message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
