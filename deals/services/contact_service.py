import logging
import re
from typing import List, Dict, Any
import time

logger = logging.getLogger(__name__)


class ContactService:
    """Сервис для работы с контактами Bitrix24"""

    def __init__(self, bitrix_token):
        self.bitrix_token = bitrix_token

    def batch_create_contacts(self, contacts_data: List[Dict]) -> List[Dict]:
        """Пакетное создание контактов через batch API"""
        results = []

        if not contacts_data:
            return results

        # Валидация данных
        validated_contacts = []
        for i, contact in enumerate(contacts_data):
            validated_contact = self._validate_contact(contact)
            if validated_contact:
                validated_contacts.append((i, validated_contact))
            else:
                results.append({
                    'success': False,
                    'error': 'Невалидные данные контакта',
                    'original_index': i
                })

        if not validated_contacts:
            return results

        # Подготавливаем команды для batch
        commands = {}
        company_names = set()

        for original_index, contact in validated_contacts:
            cmd_id = f"contact_{original_index}"

            fields = {
                'NAME': contact.get('first_name', ''),
                'LAST_NAME': contact.get('last_name', ''),
            }

            # Телефон
            if contact.get('phone'):
                phone = self._normalize_phone(contact['phone'])
                if phone:
                    fields['PHONE'] = [{'VALUE': phone, 'VALUE_TYPE': 'WORK'}]

            # Email
            if contact.get('email'):
                email = contact['email'].strip()
                if self._is_valid_email(email):
                    fields['EMAIL'] = [{'VALUE': email, 'VALUE_TYPE': 'WORK'}]

            # Компания (будем добавлять позже)
            company_name = contact.get('company_name', '').strip()
            if company_name:
                company_names.add(company_name)
                fields['COMPANY_NAME'] = company_name  # Временное поле

            commands[cmd_id] = ('crm.contact.add', {'fields': fields})

        # Выполняем batch запрос
        try:
            batch_results = self.bitrix_token.call_batch_api(commands)

            # Обрабатываем результаты
            for cmd_id, result in batch_results.items():
                original_index = int(cmd_id.split('_')[1])

                if result.get('result'):
                    contact_id = result['result']
                    results.append({
                        'success': True,
                        'contact_id': contact_id,
                        'error': None,
                        'original_index': original_index
                    })
                else:
                    error_msg = result.get('error_description', str(result.get('error', 'Unknown error')))
                    results.append({
                        'success': False,
                        'contact_id': None,
                        'error': error_msg,
                        'original_index': original_index
                    })

        except Exception as e:
            logger.error(f"Ошибка batch создания контактов: {e}")
            # Если batch не сработал, создаем по одному
            for original_index, contact in validated_contacts:
                try:
                    result = self._create_single_contact(contact)
                    result['original_index'] = original_index
                    results.append(result)
                except Exception as single_error:
                    results.append({
                        'success': False,
                        'contact_id': None,
                        'error': str(single_error),
                        'original_index': original_index
                    })

        return results

    def _create_single_contact(self, contact_data: Dict) -> Dict:
        """Создание одного контакта"""
        fields = {
            'NAME': contact_data.get('first_name', ''),
            'LAST_NAME': contact_data.get('last_name', ''),
        }

        # Телефон
        if contact_data.get('phone'):
            phone = self._normalize_phone(contact_data['phone'])
            if phone:
                fields['PHONE'] = [{'VALUE': phone, 'VALUE_TYPE': 'WORK'}]

        # Email
        if contact_data.get('email'):
            email = contact_data['email'].strip()
            if self._is_valid_email(email):
                fields['EMAIL'] = [{'VALUE': email, 'VALUE_TYPE': 'WORK'}]

        # Компания
        company_name = contact_data.get('company_name', '').strip()
        if company_name:
            company_id = self._find_or_create_company(company_name)
            if company_id:
                fields['COMPANY_ID'] = company_id

        result = self.bitrix_token.call_api_method('crm.contact.add', {
            'fields': fields
        })

        if 'result' in result:
            return {
                'success': True,
                'contact_id': result['result'],
                'error': None
            }
        else:
            error_msg = str(result.get('error', 'Unknown error'))
            return {
                'success': False,
                'contact_id': None,
                'error': error_msg
            }

    def _validate_contact(self, contact_data: Dict) -> Dict:
        """Валидация и очистка данных контакта"""
        if not contact_data:
            return None

        validated = {}

        # Обязательные поля
        first_name = contact_data.get('first_name', '').strip()
        last_name = contact_data.get('last_name', '').strip()

        if not first_name and not last_name:
            return None

        validated['first_name'] = first_name
        validated['last_name'] = last_name

        # Опциональные поля
        phone = contact_data.get('phone', '').strip()
        if phone:
            validated['phone'] = phone

        email = contact_data.get('email', '').strip()
        if email and self._is_valid_email(email):
            validated['email'] = email

        company_name = contact_data.get('company_name', '').strip()
        if company_name:
            validated['company_name'] = company_name

        return validated

    def _normalize_phone(self, phone: str) -> str:
        """Нормализация номера телефона"""
        if not phone:
            return ''

        # Убираем все нецифровые символы кроме плюса
        phone = re.sub(r'[^\d+]', '', phone)

        if not phone:
            return ''

        # Российские номера
        if phone.startswith('8') and len(phone) == 11:
            phone = '+7' + phone[1:]
        elif phone.startswith('7') and len(phone) == 11:
            phone = '+' + phone
        elif len(phone) == 10:
            phone = '+7' + phone
        elif not phone.startswith('+') and len(phone) > 10:
            phone = '+' + phone

        return phone if len(phone) >= 11 else ''

    def _is_valid_email(self, email: str) -> bool:
        """Проверка валидности email"""
        if not email:
            return False

        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _find_or_create_company(self, company_name: str) -> int:
        """Поиск или создание компании"""
        if not company_name:
            return None

        try:
            # Ищем существующую компанию
            result = self.bitrix_token.call_api_method('crm.company.list', {
                'filter': {'=TITLE': company_name},
                'select': ['ID']
            })

            if result.get('result') and len(result['result']) > 0:
                return result['result'][0]['ID']

            # Создаем новую компанию
            result = self.bitrix_token.call_api_method('crm.company.add', {
                'fields': {'TITLE': company_name}
            })

            if result.get('result'):
                return result['result']

        except Exception as e:
            logger.error(f"Ошибка работы с компанией {company_name}: {e}")

        return None

    def get_contacts(self, filters: Dict = None) -> List[Dict]:
        """Получение контактов с фильтрами"""
        if filters is None:
            filters = {}

        contacts = []
        start = 0
        limit = 50

        while True:
            try:
                result = self.bitrix_token.call_api_method('crm.contact.list', {
                    'filter': filters,
                    'select': ['ID', 'NAME', 'LAST_NAME', 'PHONE', 'EMAIL', 'COMPANY_ID', 'DATE_CREATE'],
                    'order': {'DATE_CREATE': 'DESC'},
                    'start': start
                })

                if not result or 'result' not in result or not result['result']:
                    break

                batch_contacts = result['result']
                contacts.extend(batch_contacts)

                if len(batch_contacts) < limit:
                    break

                start += limit

                # Пауза чтобы не превысить лимиты API
                time.sleep(0.1)

            except Exception as e:
                logger.error(f"Ошибка получения контактов: {e}")
                break

        return contacts

    def get_contact_companies(self, contact_ids: List[int]) -> Dict[int, str]:
        """Получение названий компаний для контактов"""
        if not contact_ids:
            return {}

        company_names = {}

        try:
            # Получаем контакты с информацией о компаниях
            commands = {}
            for i, contact_id in enumerate(contact_ids):
                commands[f"contact_{i}"] = ('crm.contact.get', {'id': contact_id})

            results = self.bitrix_token.call_batch_api(commands)

            # Собираем ID компаний
            company_ids = set()
            contact_company_map = {}

            for key, result in results.items():
                if result.get('result') and result['result'].get('COMPANY_ID'):
                    contact_id = contact_ids[int(key.split('_')[1])]
                    company_id = result['result']['COMPANY_ID']
                    company_ids.add(company_id)
                    contact_company_map[contact_id] = company_id

            # Получаем названия компаний
            if company_ids:
                company_commands = {}
                company_list = list(company_ids)

                for i, company_id in enumerate(company_list):
                    company_commands[f"company_{i}"] = ('crm.company.get', {'id': company_id})

                company_results = self.bitrix_token.call_batch_api(company_commands)

                # Сопоставляем
                for key, result in company_results.items():
                    if result.get('result'):
                        company_id = company_list[int(key.split('_')[1])]
                        company_name = result['result'].get('TITLE', '')

                        # Находим все контакты с этой компанией
                        for contact_id, comp_id in contact_company_map.items():
                            if comp_id == company_id:
                                company_names[contact_id] = company_name

        except Exception as e:
            logger.error(f"Ошибка получения компаний: {e}")

        return company_names