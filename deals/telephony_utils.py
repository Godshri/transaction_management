import random
import datetime
from django.utils import timezone


def generate_phone_number():
    """Генерирует случайный номер телефона"""
    return '+79' + ''.join([str(random.randint(0, 9)) for _ in range(9)])


def generate_external_call(but, user_id):
    """Создает тестовый внешний звонок через API телефонии"""
    try:
        duration = random.randint(65, 300)  # 1-5 минут
        call_start = timezone.now() - datetime.timedelta(hours=random.randint(0, 23))

        # Создаем звонок с обязательным полем COMMUNICATIONS
        call_result = but.call_api_method('telephony.externalcall.register', {
            'USER_ID': user_id,
            'PHONE_NUMBER': generate_phone_number(),
            'CALL_START_DATE': call_start.isoformat(),
            'TYPE': 1,  # Исходящий звонок
            'COMMUNICATIONS': [
                {
                    'ENTITY_TYPE': 'CONTACT',  # или 'LEAD', 'COMPANY', 'DEAL'
                    'ENTITY_ID': random.randint(1, 100),
                    'TYPE': 'PHONE'
                }
            ]
        })

        call_id = call_result.get('result', {}).get('CALL_ID')
        if not call_id:
            print(f"Не удалось получить CALL_ID: {call_result}")
            return False

        # Завершаем звонок
        finish_result = but.call_api_method('telephony.externalcall.finish', {
            'CALL_ID': call_id,
            'USER_ID': user_id,
            'DURATION': duration,
            'STATUS_CODE': '200',
            'RECORD_URL': ''  # Можно оставить пустым для тестов
        })

        return finish_result.get('result', False)

    except Exception as e:
        print(f"Ошибка при создании звонка: {e}")
        return False