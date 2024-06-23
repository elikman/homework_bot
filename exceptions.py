class PracticumAPIError(Exception):
    """Базовый класс для исключений, связанных с API Практикум Домашка."""


class MissingTokensError(PracticumAPIError):
    """Исключение, возникающее при отсутствии обязательных переменных
    окружения.
    """


class APIRequestError(PracticumAPIError):
    """Исключение, возникающее при ошибках запроса к API."""


class InvalidAPIResponseError(PracticumAPIError):
    """Исключение, возникающее при некорректном ответе API."""


class UnknownHomeworkStatusError(PracticumAPIError):
    """Исключение, возникающее при неизвестном статусе домашней работы."""
