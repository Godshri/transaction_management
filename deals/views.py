from linecache import cache

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.conf import settings
from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth
from integration_utils.bitrix24.bitrix_user_auth.authenticate_on_start_application import \
    authenticate_on_start_application
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_cookie import \
    get_bitrix_user_token_from_cookie, EmptyCookie
from .models import CustomDeal, ProductQRLink
import qrcode
import io
import base64
import json
from urllib.parse import urljoin
import requests
import random
from datetime import datetime, timedelta


@csrf_exempt
@main_auth(on_start=True, set_cookie=True)
def index_initial(request):
    """Первоначальная загрузка с аутентификацией через POST"""
    try:
        user = request.bitrix_user
        return render(request, 'deals/index.html', {
            'user_name': f"{user.first_name} {user.last_name}".strip() or user.email
        })
    except Exception as e:
        return render(request, 'deals/index.html')


@main_auth(on_cookies=True)
def index(request):
    """Главная страница с аутентификацией через куки"""
    try:
        user = request.bitrix_user
        return render(request, 'deals/index.html', {
            'user_name': f"{user.first_name} {user.last_name}".strip() or user.email
        })
    except Exception as e:
        return render(request, 'deals/welcome.html')


@main_auth(on_cookies=True)
def user_deals(request):
    """10 последних активных сделок пользователя"""
    try:
        token = request.bitrix_user_token

        deals = token.call_api_method('crm.deal.list', {
            'filter': {
                'ASSIGNED_BY_ID': request.bitrix_user.bitrix_id,
                'STAGE_SEMANTIC_ID': 'P'
            },
            'select': ['ID', 'TITLE', 'STAGE_ID', 'OPPORTUNITY', 'DATE_CREATE', 'UF_CRM_1757684575'],
            'order': {'DATE_CREATE': 'DESC'},
            'start': 0
        }).get('result', [])

        for deal in deals:
            priority_value = deal.get('UF_CRM_1757684575')
            priority_mapping = {
                '50': 'Низкий',
                '52': 'Средний',
                '54': 'Высокий',
                'high': 'Высокий',
                'medium': 'Средний',
                'low': 'Низкий'
            }
            deal['formatted_priority'] = priority_mapping.get(str(priority_value), 'Не указан')

        return render(request, 'deals/deals.html', {
            'deals': deals[:10]
        })
    except Exception as e:
        return HttpResponse(f"Ошибка при получении сделок: {str(e)}", status=500)


@main_auth(on_cookies=True)
def create_deal(request):
    """Форма создания сделки"""
    try:
        if request.method == 'POST':
            token = request.bitrix_user_token

            title = request.POST.get('title')
            opportunity = request.POST.get('opportunity', 0)
            custom_priority = request.POST.get('custom_priority')
            description = request.POST.get('description', '')

            priority_mapping = {
                'high': '54',
                'medium': '52',
                'low': '50'
            }
            bitrix_priority = priority_mapping.get(custom_priority, '52')

            result = token.call_api_method('crm.deal.add', {
                'fields': {
                    'TITLE': title,
                    'OPPORTUNITY': opportunity,
                    'ASSIGNED_BY_ID': request.bitrix_user.bitrix_id,
                    'UF_CRM_1757684575': bitrix_priority,
                    'COMMENTS': description,
                    'CATEGORY_ID': 0
                }
            })

            deal_id = result.get('result')

            if deal_id:
                CustomDeal.objects.create(
                    bitrix_id=deal_id,
                    title=title,
                    custom_priority=custom_priority
                )

            return redirect('deals')

        return render(request, 'deals/create_deal.html')
    except Exception as e:
        return HttpResponse(f"Ошибка при создании сделки: {str(e)}", status=500)


@main_auth(on_cookies=True)
def generate_qr(request):
    """Генерация QR-кода для товара"""
    if request.method == 'POST':
        try:
            product_id = request.POST.get('product_id')
            if not product_id:
                return HttpResponseBadRequest("Не указан ID товара")

            try:
                product_id_int = int(product_id)
            except ValueError:
                return HttpResponseBadRequest("ID товара должен быть числом")

            token = request.bitrix_user_token

            product_result = token.call_api_method('crm.product.get', {
                'id': product_id_int
            })

            if 'result' not in product_result:
                return HttpResponseBadRequest("Товар не найден")

            product = product_result['result']
            product_name = product.get('NAME', 'Неизвестный товар')

            images = []

            property_44 = product.get('PROPERTY_44')
            if property_44 and isinstance(property_44, list):
                for i, img_data in enumerate(property_44):
                    if isinstance(img_data, dict) and 'value' in img_data:
                        value_data = img_data['value']
                        if isinstance(value_data, dict):

                            download_url = value_data.get('downloadUrl')
                            if download_url:

                                if not download_url.startswith(('http://', 'https://')):
                                    download_url = f"https://b24-oyi9l4.bitrix24.ru{download_url}"

                                images.append({
                                    'id': f'image_{i}',
                                    'src': download_url,
                                    'title': f'Изображение {i + 1}'
                                })


            other_image_fields = ['PREVIEW_PICTURE', 'DETAIL_PICTURE', 'MORE_PHOTO']
            for field in other_image_fields:
                field_value = product.get(field)
                if field_value:

                    if isinstance(field_value, list):
                        for i, img_data in enumerate(field_value):
                            if isinstance(img_data, dict) and 'downloadUrl' in img_data:
                                download_url = img_data.get('downloadUrl')
                                if download_url:
                                    if not download_url.startswith(('http://', 'https://')):
                                        download_url = f"https://b24-oyi9l4.bitrix24.ru{download_url}"

                                    images.append({
                                        'id': f'{field}_{i}',
                                        'src': download_url,
                                        'title': f'{field} {i + 1}'
                                    })
                    elif isinstance(field_value, dict) and 'downloadUrl' in field_value:

                        download_url = field_value.get('downloadUrl')
                        if download_url:
                            if not download_url.startswith(('http://', 'https://')):
                                download_url = f"https://b24-oyi9l4.bitrix24.ru{download_url}"

                            images.append({
                                'id': field,
                                'src': download_url,
                                'title': field.replace('_', ' ').title()
                            })

            product_data = {
                'NAME': product_name,
                'PRICE': product.get('PRICE'),
                'DESCRIPTION': product.get('DESCRIPTION') or product.get('PREVIEW_TEXT') or product.get('DETAIL_TEXT'),
                'CURRENCY_ID': product.get('CURRENCY_ID'),
                'MEASURE': product.get('MEASURE'),
                'SECTION_ID': product.get('SECTION_ID'),
            }

            # Создаем секретную ссылку с сохраненными данными
            qr_link = ProductQRLink.objects.create(
                product_id=product_id_int,
                product_name=product_name,
                product_data=product_data,
                product_images=images,
                created_by=request.bitrix_user
            )

            base_url = request.build_absolute_uri('/')[:-1]
            product_url = urljoin(base_url, qr_link.get_absolute_url())

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(product_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode()

            return render(request, 'deals/qr_result.html', {
                'qr_image': img_str,
                'product_url': product_url,
                'product_name': product_name,
                'product_id': product_id_int
            })

        except Exception as e:
            return HttpResponse(f"Ошибка при генерации QR-кода: {str(e)}", status=500)

    return render(request, 'deals/generate_qr.html')



def product_qr_detail(request, uuid):
    """Страница товара по секретной ссылке"""
    try:
        qr_link = ProductQRLink.objects.get(id=uuid, is_active=True)
        product_data = qr_link.product_data or {}
        product_images = qr_link.product_images or []

        def get_image_url(image_id):
            if not image_id:
                return None
            return f"https://b24-oyi9l4.bitrix24.ru/bitrix/components/bitrix/main.show/templates/.default/images/no_photo.png?{image_id}"

        for img in product_images:
            if 'src' in img and img['src']:
                if isinstance(img['src'], str) and img['src'].startswith(('http://', 'https://')):
                    continue
                img['src'] = get_image_url(img['src'])

        return render(request, 'deals/product_detail.html', {
            'qr_link': qr_link,
            'product_data': product_data,
            'product_images': product_images,
            'error_message': None
        })

    except ProductQRLink.DoesNotExist:
        return HttpResponse("Страница не найдена или ссылка недействительна", status=404)
    except Exception as e:
        print(f"Unexpected error: {e}")
        return HttpResponse("Ошибка сервера", status=500)

@main_auth(on_cookies=True)
def search_products(request):
    """Поиск товаров для автокомплита"""
    try:
        query = request.GET.get('q', '')
        if not query:
            return JsonResponse({'results': []})

        token = request.bitrix_user_token

        products_result = token.call_api_method('crm.product.list', {
            'filter': {'%NAME': query},
            'select': ['ID', 'NAME', 'PRICE', 'DESCRIPTION', 'PREVIEW_PICTURE', 'PROPERTY_44'],
            'order': {'NAME': 'ASC'},
            'start': 0
        })

        products = products_result.get('result', [])

        results = []
        for product in products[:10]:
            main_image = None
            if product.get('PREVIEW_PICTURE'):
                main_image = product.get('PREVIEW_PICTURE')
            elif product.get('PROPERTY_44'):
                prop_44 = product['PROPERTY_44']
                if isinstance(prop_44, list) and prop_44:
                    main_image = prop_44[0]
                elif prop_44:
                    main_image = prop_44

            results.append({
                'id': product['ID'],
                'text': f"{product['NAME']} (ID: {product['ID']})",
                'name': product['NAME'],
                'price': product.get('PRICE', 0),
                'image': main_image
            })

        return JsonResponse({'results': results})

    except Exception as e:
        return JsonResponse({'results': []})


@main_auth(on_cookies=True)
def get_product_details(request):
    """Получение полной информации о товаре"""
    try:
        product_id = request.GET.get('id')
        if not product_id:
            return JsonResponse({'success': False, 'error': 'ID товара не указан'})

        token = request.bitrix_user_token

        product_result = token.call_api_method('crm.product.get', {
            'id': int(product_id)
        })

        if 'result' not in product_result:
            return JsonResponse({'success': False, 'error': 'Товар не найден'})

        product = product_result['result']

        image_url = None
        if product.get('PREVIEW_PICTURE'):
            image_data = product['PREVIEW_PICTURE']
            if isinstance(image_data, dict) and 'downloadUrl' in image_data:
                image_url = image_data['downloadUrl']
                if not image_url.startswith(('http://', 'https://')):
                    image_url = f"https://b24-oyi9l4.bitrix24.ru{image_url}"

        return JsonResponse({
            'success': True,
            'product': {
                'id': product.get('ID'),
                'name': product.get('NAME', 'Неизвестный товар'),
                'price': product.get('PRICE', 0),
                'description': product.get('DESCRIPTION') or product.get('PREVIEW_TEXT') or product.get(
                    'DETAIL_TEXT') or 'Не указано',
                'image': image_url
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@main_auth(on_cookies=True)
def employees_table(request):
    """Таблица сотрудников с руководителями и статистикой звонков"""
    try:
        token = request.bitrix_user_token

        # Получаем всех активных пользователей с полной информацией
        users_result = token.call_api_method('user.get', {
            'filter': {'ACTIVE': True},
            'select': ['ID', 'NAME', 'LAST_NAME', 'SECOND_NAME', 'UF_DEPARTMENT', 'WORK_POSITION', 'UF_HEAD']
        })

        active_users = users_result.get('result', [])

        # Получаем структуру департаментов
        departments_result = token.call_api_method('department.get', {})
        departments = {dept['ID']: dept for dept in departments_result.get('result', [])}

        # Получаем статистику звонков за последние 24 часа
        call_stats = get_call_statistics(token)

        # Формируем данные для таблицы
        employees_data = []
        for user in active_users:
            user_id = user['ID']
            full_name = f"{user.get('LAST_NAME', '')} {user.get('NAME', '')} {user.get('SECOND_NAME', '')}".strip()

            # Получаем цепочку руководителей (исправленная версия)
            managers = get_manager_chain(user, departments, active_users)

            # Получаем количество звонков
            call_count = call_stats.get(str(user_id), 0)

            employees_data.append({
                'id': user_id,
                'name': full_name,
                'position': user.get('WORK_POSITION', ''),
                'managers': managers,
                'call_count': call_count
            })

        return render(request, 'deals/employees_table.html', {
            'employees': employees_data,
            'user_name': f"{request.bitrix_user.first_name} {request.bitrix_user.last_name}".strip() or request.bitrix_user.email
        })

    except Exception as e:
        return HttpResponse(f"Ошибка при получении данных сотрудников: {str(e)}", status=500)


def get_manager_chain(user, departments, all_users):
    """Получает цепочку руководителей (исправленная версия)"""
    managers = []
    current_user = user
    processed_users = set()  # Для избежания циклов
    max_depth = 10
    depth = 0

    while depth < max_depth:
        user_id = str(current_user['ID'])

        # Проверяем, не обрабатывали ли уже этого пользователя
        if user_id in processed_users:
            break
        processed_users.add(user_id)

        # 1. Проверяем прямого руководителя (UF_HEAD)
        head_id = current_user.get('UF_HEAD')
        if head_id:
            head_user = next((u for u in all_users if str(u['ID']) == str(head_id)), None)
            if head_user:
                head_name = f"{head_user.get('LAST_NAME', '')} {head_user.get('NAME', '')}".strip()
                if head_name:  # Добавляем только если есть имя
                    # Проверяем, не добавляли ли уже этого руководителя
                    if not any(m['id'] == head_id for m in managers):
                        managers.append({
                            'id': head_id,
                            'name': head_name
                        })
                current_user = head_user
                depth += 1
                continue

        # 2. Проверяем руководителей через департаменты
        user_departments = current_user.get('UF_DEPARTMENT', [])
        if not user_departments:
            break

        dept_found = False
        for dept_id in user_departments:
            department = departments.get(str(dept_id))
            if not department:
                continue

            dept_head_id = department.get('UF_HEAD')
            if dept_head_id and str(dept_head_id) != str(current_user['ID']):
                head_user = next((u for u in all_users if str(u['ID']) == str(dept_head_id)), None)
                if head_user:
                    head_name = f"{head_user.get('LAST_NAME', '')} {head_user.get('NAME', '')}".strip()
                    if head_name:
                        # Проверяем, не добавляли ли уже этого руководителя
                        if not any(m['id'] == dept_head_id for m in managers):
                            managers.append({
                                'id': dept_head_id,
                                'name': head_name
                            })
                    current_user = head_user
                    dept_found = True
                    depth += 1
                    break

        if not dept_found:
            break

    return managers


def get_call_statistics(token):
    """Получает статистику звонков через метод voximplant.statistic.get"""
    try:
        # Проверяем тестовые данные
        from django.core.cache import cache
        test_data = cache.get('test_call_stats')
        if test_data:
            return test_data

        end_date = datetime.now()
        start_date = end_date - timedelta(hours=24)

        call_stats = {}

        # Пробуем получить через voximplant
        voximplant_calls = get_voximplant_statistics(token, start_date, end_date)

        if voximplant_calls:
            # Обрабатываем данные voximplant
            for call in voximplant_calls:
                user_id = call.get('PORTAL_USER_ID')
                if user_id:
                    user_id_str = str(user_id)
                    call_stats[user_id_str] = call_stats.get(user_id_str, 0) + 1
        else:
            # Fallback на CRM деятельность
            activities_result = token.call_api_method('crm.activity.list', {
                'filter': {
                    '>=CREATED': start_date.strftime('%Y-%m-%dT%H:%M:%S'),
                    '<=CREATED': end_date.strftime('%Y-%m-%dT%H:%M:%S'),
                    'TYPE_ID': 2  # Звонки
                },
                'select': ['ID', 'OWNER_ID', 'OWNER_TYPE_ID', 'CREATED']
            })

            for activity in activities_result.get('result', []):
                owner_id = activity.get('OWNER_ID')
                if owner_id:
                    call_stats[str(owner_id)] = call_stats.get(str(owner_id), 0) + 1

        return call_stats

    except Exception as e:
        print(f"Общая ошибка при получении статистики звонков: {e}")
        return {}


def generate_test_call_data():
    """Генерирует тестовые данные о звонках"""
    # Для демонстрации создаем случайные данные
    import random
    return {str(i): random.randint(0, 10) for i in range(1, 20)}


@main_auth(on_cookies=True)
def generate_test_calls(request):
    """Генерация тестовых данных о звонках с использованием voximplant API"""
    try:
        token = request.bitrix_user_token

        # Получаем активных пользователей
        users_result = token.call_api_method('user.get', {
            'filter': {'ACTIVE': True},
            'select': ['ID', 'NAME', 'LAST_NAME']
        })

        users = users_result.get('result', [])
        if not users:
            return JsonResponse({'success': False, 'error': 'Нет активных пользователей'})

        created_count = 0
        test_stats = {}

        # Создаем тестовые записи звонков
        for user in users:
            user_id = user['ID']
            call_count = random.randint(1, 8)  # 1-8 звонков на пользователя

            # Сохраняем количество звонков для статистики
            test_stats[str(user_id)] = call_count
            created_count += call_count

        # Сохраняем тестовые данные в кэш (или в сессию)
        from django.core.cache import cache
        cache.set('test_call_stats', test_stats, timeout=3600)  # Храним 1 час

        return JsonResponse({
            'success': True,
            'message': f'Создано {created_count} тестовых записей о звонках',
            'calls_created': created_count,
            'test_data': test_stats
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_voximplant_statistics(token, start_date, end_date):
    """Специализированная функция для получения статистики через voximplant"""
    try:
        voximplant_result = token.call_api_method('voximplant.statistic.get', {
            'FILTER': {
                '>=CALL_START_DATE': start_date.strftime('%Y-%m-%dT%H:%M:%S'),
                '<=CALL_START_DATE': end_date.strftime('%Y-%m-%dT%H:%M:%S')
            },
            'SORT': 'CALL_START_DATE',
            'ORDER': 'DESC'
        })

        return voximplant_result.get('result', [])

    except Exception as e:
        # Проверяем, есть ли у пользователя права на доступ к telephony
        if "access denied" in str(e).lower() or "permission" in str(e).lower():
            print("У пользователя нет прав доступа к статистике телефонии")
        else:
            print(f"Ошибка voximplant API: {e}")
        return []