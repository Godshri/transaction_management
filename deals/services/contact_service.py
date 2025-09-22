import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class ContactService:
    """Сервис для работы с контактами Bitrix24"""

    def __init__(self, bitrix_token):
        self.bitrix_token = bitrix_token

    def batch_create_contacts(self, contacts_data: List[Dict]) -> List[Dict]:
        """Пакетное создание контактов"""
        results = []

        # Валидация и очистка данных
        validated_contacts = []
        for contact in contacts_data:
            validated_contact = self._validate_contact(contact)
            if validated_contact:
                validated_contacts.append(validated_contact)

        if not validated_contacts:
            return [{'success': False, 'error': 'Нет валидных контактов'} for _ in contacts_data]

        # Группируем компании для поиска
        company_names = list(set(
            contact['company_name'] for contact in validated_contacts
            if contact.get('company_name')
        ))

        # Получаем ID компаний по названиям
        company_ids = self._get_company_ids_by_names(company_names)

        # Подготавливаем команды для batch-запроса
        commands = []
        for contact_data in validated_contacts:
            company_id = company_ids.get(contact_data.get('company_name', '').strip())

            fields = {
                'NAME': contact_data.get('first_name', ''),
                'LAST_NAME': contact_data.get('last_name', ''),
            }

            # Добавляем телефон если есть
            if contact_data.get('phone'):
                phone = self._normalize_phone(contact_data['phone'])
                if phone:
                    fields['PHONE'] = [{'VALUE': phone, 'VALUE_TYPE': 'WORK'}]

            # Добавляем email если есть
            if contact_data.get('email'):
                email = contact_data['email'].strip()
                if self._is_valid_email(email):
                    fields['EMAIL'] = [{'VALUE': email, 'VALUE_TYPE': 'WORK'}]

            # Добавляем компанию если найдена
            if company_id:
                fields['COMPANY_ID'] = company_id

            commands.append(('crm.contact.add', {'fields': fields}))

        # Выполняем batch-запрос
        if commands:
            try:
                batch_results = self.bitrix_token.call_batch_api(commands)

                for i, result in enumerate(batch_results):
                    if 'result' in result and result['result']:
                        results.append({
                            'success': True,
                            'contact_id': result['result'],
                            'error': None
                        })
                    else:
                        error_msg = str(result.get('error', 'Unknown error'))
                        results.append({
                            'success': False,
                            'contact_id': None,
                            'error': error_msg
                        })
            except Exception as e:
                logger.error(f"Ошибка batch-запроса: {e}")
                results = [{'success': False, 'error': str(e)} for _ in validated_contacts]
        else:
            results = [{'success': False, 'error': 'No contacts to process'} for _ in validated_contacts]

        return results

    def _validate_contact(self, contact_data: Dict) -> Dict:
        """Валидация и очистка данных контакта"""
        validated = {}

        # Имя и фамилия обязательны
        first_name = contact_data.get('first_name', '').strip()
        last_name = contact_data.get('last_name', '').strip()

        if not first_name and not last_name:
            return None

        validated['first_name'] = first_name
        validated['last_name'] = last_name

        # Телефон
        phone = contact_data.get('phone', '').strip()
        if phone:
            validated['phone'] = phone

        # Email
        email = contact_data.get('email', '').strip()
        if email and self._is_valid_email(email):
            validated['email'] = email

        # Компания
        company_name = contact_data.get('company_name', '').strip()
        if company_name:
            validated['company_name'] = company_name

        return validated

    def _normalize_phone(self, phone: str) -> str:
        """Нормализация номера телефона"""
        # Убираем все нецифровые символы кроме плюса
        phone = re.sub(r'[^\d+]', '', phone)

        # Если номер начинается с 8, заменяем на +7
        if phone.startswith('8'):
            phone = '+7' + phone[1:]

        # Если номер без кода страны, добавляем +7
        if phone and not phone.startswith('+'):
            if len(phone) == 10:
                phone = '+7' + phone
            elif len(phone) == 11 and phone.startswith('7'):
                phone = '+' + phone

        return phone if len(phone) >= 11 else ''

    def _is_valid_email(self, email: str) -> bool:
        """Проверка валидности email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _get_company_ids_by_names(self, company_names: List[str]) -> Dict[str, int]:
        """Получение ID компаний по названиям"""
        if not company_names:
            return {}

        company_ids = {}

        # Ищем компании по названиям
        for company_name in company_names:
            if not company_name:
                continue

            result = self.bitrix_token.call_api_method('crm.company.list', {
                'filter': {'TITLE': company_name},
                'select': ['ID', 'TITLE']
            })

            if result.get('result') and isinstance(result['result'], list):
                for company in result['result']:
                    if company.get('TITLE') == company_name:
                        company_ids[company_name] = company['ID']
                        break

        return company_ids

    def get_contacts(self, filters: Dict = None) -> List[Dict]:
        """Получение контактов с фильтрами"""
        if filters is None:
            filters = {}

        contacts = []
        start = 0
        limit = 50

        while True:
            result = self.bitrix_token.call_api_method('crm.contact.list', {
                'filter': filters,
                'select': ['ID', 'NAME', 'LAST_NAME', 'PHONE', 'EMAIL', 'COMPANY_ID', 'DATE_CREATE'],
                'order': {'DATE_CREATE': 'DESC'},
                'start': start
            })

            if not result or 'result' not in result or not result['result']:
                break

            contacts.extend(result['result'])

            if len(result['result']) < limit:
                break

            start += limit

        return contacts

    def get_contact_companies(self, contact_ids: List[int]) -> Dict[int, str]:
        """Получение названий компаний для контактов"""
        if not contact_ids:
            return {}

        company_names = {}

        # Получаем информацию о компаниях
        company_ids = set()
        contacts_with_companies = {}

        # Сначала получаем все контакты с компаниями
        for contact_id in contact_ids:
            result = self.bitrix_token.call_api_method('crm.contact.get', {
                'id': contact_id,
                'select': ['COMPANY_ID']
            })

            if result.get('result') and result['result'].get('COMPANY_ID'):
                company_id = result['result']['COMPANY_ID']
                company_ids.add(company_id)
                contacts_with_companies[contact_id] = company_id

        # Получаем названия компаний
        if company_ids:
            companies_result = self.bitrix_token.call_api_method('crm.company.list', {
                'filter': {'ID': list(company_ids)},
                'select': ['ID', 'TITLE']
            })

            if companies_result.get('result'):
                company_id_to_name = {
                    company['ID']: company.get('TITLE', '')
                    for company in companies_result['result']
                }

                # Сопоставляем контакты с названиями компаний
                for contact_id, company_id in contacts_with_companies.items():
                    company_names[contact_id] = company_id_to_name.get(company_id, '')

        return company_names