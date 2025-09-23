from linecache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from django.conf import settings
from django.utils import  timezone
from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth
from integration_utils.bitrix24.bitrix_user_auth.authenticate_on_start_application import \
    authenticate_on_start_application
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_cookie import \
    get_bitrix_user_token_from_cookie, EmptyCookie
from .models import CustomDeal, ProductQRLink, ImportExportJob, ImportExportRecord
import qrcode
import io
import base64
import json
from urllib.parse import urljoin
import requests
import random
import logging
from datetime import datetime, timedelta
from . import telephony_utils
from .telephony_utils import generate_external_call
import os
from django.core.cache import cache
import csv
from .file_handlers.base_handler import FileHandlerFactory
from .services.contact_service import ContactService
import time
from django.db import transaction

logger = logging.getLogger(__name__)


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


        users_result = token.call_api_method('user.get', {
            'filter': {'ACTIVE': True},
            'select': ['ID', 'NAME', 'LAST_NAME', 'SECOND_NAME', 'UF_DEPARTMENT', 'WORK_POSITION', 'UF_HEAD', 'EMAIL'],
            'order': {'LAST_NAME': 'ASC'}
        })

        active_users = users_result.get('result', [])
        if not isinstance(active_users, list):
            active_users = []


        departments_result = token.call_api_method('department.get', {})
        departments = departments_result.get('result', [])
        if not isinstance(departments, list):
            departments = []


        call_stats = get_call_statistics(token)

        call_count_by_user = {}
        for call in call_stats:
            if isinstance(call, dict):
                user_id = call.get('PORTAL_USER_ID')
                if user_id:
                    user_id_str = str(user_id)
                    call_count_by_user[user_id_str] = call_count_by_user.get(user_id_str, 0) + 1


        employees_data = []
        for user in active_users:
            if not isinstance(user, dict):
                continue

            user_id = user.get('ID')
            if not user_id:
                continue

            full_name = f"{user.get('LAST_NAME', '')} {user.get('NAME', '')} {user.get('SECOND_NAME', '')}".strip()
            if not full_name.strip():
                full_name = user.get('EMAIL', 'Без имени')

            managers = get_manager_chain(user, departments, active_users)

            user_id_str = str(user_id)
            call_count = call_count_by_user.get(user_id_str, 0)

            employees_data.append({
                'id': user_id,
                'name': full_name,
                'position': user.get('WORK_POSITION', 'Не указана'),
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
    """Получает цепочку руководителей с учетом иерархии отделов"""
    managers = []
    processed_users = set()

    current_user_id = str(user.get('ID'))
    users_by_id = {str(u['ID']): u for u in all_users}
    departments_by_id = {str(dept['ID']): dept for dept in departments}


    direct_head_id = user.get('UF_HEAD')
    if direct_head_id:
        direct_head_id_str = str(direct_head_id)
        if (direct_head_id_str != current_user_id and
                direct_head_id_str not in processed_users):

            direct_head_user = users_by_id.get(direct_head_id_str)
            if direct_head_user:
                direct_head_name = get_user_full_name(direct_head_user)
                if direct_head_name:
                    managers.append({
                        'id': direct_head_id,
                        'name': direct_head_name
                    })
                    processed_users.add(direct_head_id_str)


    user_departments = normalize_department_ids(user.get('UF_DEPARTMENT', []))

    for dept_id in user_departments:
        dept = departments_by_id.get(str(dept_id))
        if not dept:
            continue


        dept_head_id = dept.get('UF_HEAD')
        if dept_head_id:
            dept_head_id_str = str(dept_head_id)
            if (dept_head_id_str != current_user_id and
                    dept_head_id_str not in processed_users):

                dept_head_user = users_by_id.get(dept_head_id_str)
                if dept_head_user:
                    dept_head_name = get_user_full_name(dept_head_user)
                    if dept_head_name:
                        managers.append({
                            'id': dept_head_id,
                            'name': dept_head_name
                        })
                        processed_users.add(dept_head_id_str)

        parent_dept_id = dept.get('PARENT')
        while parent_dept_id:
            parent_dept = departments_by_id.get(str(parent_dept_id))
            if not parent_dept:
                break

            parent_head_id = parent_dept.get('UF_HEAD')
            if parent_head_id:
                parent_head_id_str = str(parent_head_id)
                if (parent_head_id_str != current_user_id and
                        parent_head_id_str not in processed_users):

                    parent_head_user = users_by_id.get(parent_head_id_str)
                    if parent_head_user:
                        parent_head_name = get_user_full_name(parent_head_user)
                        if parent_head_name:
                            managers.append({
                                'id': parent_head_id,
                                'name': parent_head_name
                            })
                            processed_users.add(parent_head_id_str)

            parent_dept_id = parent_dept.get('PARENT')

    return managers


def get_user_full_name(user_data):
    """Формирует полное имя пользователя"""
    last_name = user_data.get('LAST_NAME', '').strip()
    first_name = user_data.get('NAME', '').strip()
    middle_name = user_data.get('SECOND_NAME', '').strip()

    full_name = f"{last_name} {first_name} {middle_name}".strip()
    if not full_name:
        full_name = user_data.get('EMAIL', 'Без имени')

    return full_name


def normalize_department_ids(dept_ids):
    """Нормализует ID отделов к списку чисел"""
    if not dept_ids:
        return []

    if isinstance(dept_ids, str):
        try:
            return [int(dept_ids)]
        except ValueError:
            return []

    if isinstance(dept_ids, list):
        normalized = []
        for dept_id in dept_ids:
            if isinstance(dept_id, (int, float)):
                normalized.append(int(dept_id))
            elif isinstance(dept_id, str) and dept_id.isdigit():
                normalized.append(int(dept_id))
        return normalized

    return []


def get_call_statistics(token):
    """Получает статистику звонков через voximplant API с пагинацией"""
    try:
        all_calls = []
        start = 0
        limit = 50


        filter_date = (timezone.now() - timedelta(hours=24)).isoformat()

        while True:
            calls_result = token.call_api_method('voximplant.statistic.get', {
                'FILTER': {
                    '>CALL_START_DATE': filter_date,
                    'CALL_TYPE': 1,
                    '>CALL_DURATION': 60
                },
                'ORDER': {'CALL_START_DATE': 'DESC'},
                'start': start
            })

            if not calls_result or 'result' not in calls_result:
                break

            calls = calls_result['result']
            if not calls or not isinstance(calls, list):
                break

            all_calls.extend(calls)

            if len(calls) < limit:
                break

            start += limit

        return all_calls

    except Exception as e:
        print(f"Ошибка при получении статистики звонков: {e}")
        return []

@main_auth(on_cookies=True)
def generate_test_calls(request):
    """Генерация тестовых звонков через API телефонии"""
    try:
        token = request.bitrix_user_token


        users_result = token.call_api_method('user.get', {
            'filter': {'ACTIVE': True},
            'select': ['ID', 'NAME', 'LAST_NAME']
        })

        users = users_result.get('result', [])
        if not users:
            return JsonResponse({'success': False, 'error': 'Нет активных пользователей'})

        created_count = 0
        test_stats = {}

        for user in users:
            user_id = user['ID']
            call_count = random.randint(1, 8)

            user_calls_created = 0
            for i in range(call_count):
                try:
                    success = generate_external_call(token, user_id)
                    if success:
                        user_calls_created += 1

                except Exception as e:
                    print(f"Ошибка при создании звонка: {e}")
                    continue

            test_stats[str(user_id)] = user_calls_created
            created_count += user_calls_created

        return JsonResponse({
            'success': True,
            'message': f'Создано {created_count} тестовых звонков',
            'calls_created': created_count,
            'test_data': test_stats
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def get_geocode(address_data):
    """Получение координат по адресу"""
    try:
        address_parts = [
            address_data.get('ADDRESS_1'),
            address_data.get('CITY'),
            address_data.get('REGION'),
            address_data.get('PROVINCE'),
            address_data.get('COUNTRY')
        ]
        address = ' '.join(filter(None, address_parts))

        if not address:
            return None

        cache_key = f'geocode_{hash(address)}'
        cached_coords = cache.get(cache_key)
        if cached_coords:
            return cached_coords

        api_key = os.environ.get('YANDEX_API_KEY', '398bf0ac-876c-44ac-a830-0b7e29f5f4f9')

        response = requests.get(
            f'https://geocode-maps.yandex.ru/1.x/',
            params={
                'apikey': api_key,
                'geocode': address,
                'format': 'json'
            },
            timeout=10
        )

        response.raise_for_status()
        data = response.json()

        feature_member = data['response']['GeoObjectCollection']['featureMember']
        if not feature_member:
            return None

        pos = feature_member[0]['GeoObject']['Point']['pos']
        longitude, latitude = map(float, pos.split(' '))
        coords = [latitude, longitude]

        cache.set(cache_key, coords, timeout=60 * 60 * 24 * 30)

        return coords

    except Exception as e:
        logger.warning(f"Ошибка геокодирования адреса: {e}")
        return None


def get_logo(company):
    """Получение логотипа компании"""
    try:
        logo_data = company.get('LOGO')
        if not logo_data:
            return None

        cache_key = f'logo_{company["ID"]}'
        cached_logo_url = cache.get(cache_key)
        if cached_logo_url:
            return cached_logo_url

        bitrix_domain = os.environ.get('BITRIX_DOMAIN', 'b24-oyi9l4.bitrix24.ru')
        root_url = os.environ.get('ROOT_URL', 'http://localhost:8000')

        download_url = logo_data.get('downloadUrl')
        if not download_url:
            return None

        if download_url.startswith(('http://', 'https://')):
            full_url = download_url
        else:
            full_url = f'https://{bitrix_domain}{download_url}'

        logo_dir = os.path.join(settings.MEDIA_ROOT, 'company_logos')
        os.makedirs(logo_dir, exist_ok=True)

        file_name = f"logo_{company['ID']}.png"
        file_path = os.path.join(logo_dir, file_name)

        if os.path.exists(file_path):
            relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
            logo_url = f"{root_url}{settings.MEDIA_URL}{relative_path}".replace('\\', '/')
            cache.set(cache_key, logo_url, timeout=60 * 60 * 24 * 30)
            return logo_url

        response = requests.get(full_url, timeout=10)
        response.raise_for_status()

        with open(file_path, 'wb') as f:
            f.write(response.content)

        relative_path = os.path.relpath(file_path, settings.MEDIA_ROOT)
        logo_url = f"{root_url}{settings.MEDIA_URL}{relative_path}".replace('\\', '/')
        cache.set(cache_key, logo_url, timeout=60 * 60 * 24 * 30)
        return logo_url

    except Exception as e:
        logger.warning(f"Ошибка загрузки логотипа компании {company.get('ID')}: {e}")
        return None


@main_auth(on_cookies=True)
def company_map(request):
    """Карта с адресами компаний"""
    try:
        but = request.bitrix_user_token

        companies = but.call_list_method('crm.company.list', {
            'select': ['ID', 'TITLE', 'LOGO', 'ADDRESS', 'COMMENTS'],
            'order': {'DATE_CREATE': 'DESC'}
        })

        companies_dict = {company['ID']: company for company in companies}

        addresses = but.call_list_method('crm.address.list', {
            'filter': {'ENTITY_TYPE_ID': 4},
            'select': ['ENTITY_ID', 'ADDRESS_1', 'CITY', 'REGION', 'PROVINCE', 'COUNTRY']
        })

        addresses_dict = {}
        for address in addresses:
            company_id = address['ENTITY_ID']
            addresses_dict[company_id] = address

        points = []
        geocoded_count = 0

        for company in companies:
            company_id = company['ID']
            address = addresses_dict.get(company_id)

            if address:
                geocode = get_geocode(address)

                if geocode:
                    geocoded_count += 1

                    full_address = format_address(address)

                    logo_url = get_logo(company)

                    point = {
                        'TITLE': company['TITLE'],
                        'DESCRIPTION': company.get('COMMENTS', ''),
                        'ADDRESS': full_address,
                        'GEOCODE': geocode,
                        'LogoURL': logo_url
                    }
                    points.append(point)

        logger.info(f"Загружено {len(points)} компаний с координатами из {len(companies)} всего")

        return render(request, 'deals/company_map.html', {
            'points': points,
            'error': None,
            'user_name': f"{request.bitrix_user.first_name} {request.bitrix_user.last_name}".strip() or request.bitrix_user.email,
            'yandex_api_key': settings.YANDEX_MAPS_API_KEY
        })

    except Exception as e:
        error_message = f"Ошибка при загрузке карты компаний: {str(e)}"
        logger.error(error_message)
        return render(request, 'deals/company_map.html', {
            'points': [],
            'error': error_message,
            'user_name': f"{request.bitrix_user.first_name} {request.bitrix_user.last_name}".strip() or request.bitrix_user.email,
            'yandex_api_key': settings.YANDEX_MAPS_API_KEY
        })


def format_address(address_data):
    """Форматирует адрес в читаемый вид"""
    address_parts = [
        address_data.get('ADDRESS_1'),
        address_data.get('CITY'),
        address_data.get('REGION'),
        address_data.get('PROVINCE'),
        address_data.get('COUNTRY')
    ]

    formatted_address = ', '.join(filter(None, address_parts))
    return formatted_address


@main_auth(on_cookies=True)
def contacts_import_export(request):
    """Главная страница импорта/экспорта контактов"""
    return render(request, 'deals/contacts_import_export.html', {
        'user_name': f"{request.bitrix_user.first_name} {request.bitrix_user.last_name}".strip() or request.bitrix_user.email
    })


@main_auth(on_cookies=True)
@csrf_exempt
def import_contacts(request):
    """Импорт контактов из файла"""
    if request.method == 'POST':
        try:
            file = request.FILES.get('file')
            file_format = request.POST.get('format', 'csv')

            if not file:
                return JsonResponse({'success': False, 'error': 'Файл не загружен'})

            job = ImportExportJob.objects.create(
                job_type=ImportExportJob.JOB_TYPE_IMPORT,
                file_format=file_format,
                created_by=request.bitrix_user,
                file_name=file.name,
                status=ImportExportJob.STATUS_PENDING
            )


            success = process_import_file(job.id, file, file_format, request.bitrix_user_token)

            if success:
                return JsonResponse({
                    'success': True,
                    'job_id': str(job.id),
                    'message': 'Импорт завершен успешно!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Ошибка при импорте контактов'
                })

        except Exception as e:
            logger.error(f"Ошибка импорта контактов: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})


@main_auth(on_cookies=True)
@csrf_exempt
def export_contacts(request):
    """Экспорт контактов в файл"""
    if request.method == 'POST':
        try:
            file_format = request.POST.get('format', 'csv')
            date_filter = request.POST.get('date_filter', 'all')

            filters = {}
            if date_filter == 'today':
                filters['>=DATE_CREATE'] = datetime.now().strftime('%Y-%m-%d')
            elif date_filter == 'yesterday':
                yesterday = datetime.now() - timedelta(days=1)
                filters['DATE_CREATE'] = yesterday.strftime('%Y-%m-%d')
            elif date_filter == 'last_week':
                last_week = datetime.now() - timedelta(days=7)
                filters['>=DATE_CREATE'] = last_week.strftime('%Y-%m-%d')


            job = ImportExportJob.objects.create(
                job_type=ImportExportJob.JOB_TYPE_EXPORT,
                file_format=file_format,
                created_by=request.bitrix_user,
                file_name=f"contacts_export.{file_format}",
                filter_params=filters,
                status=ImportExportJob.STATUS_PENDING
            )

            success = process_export(job.id, filters, file_format, request.bitrix_user_token)

            if success:
                return JsonResponse({
                    'success': True,
                    'job_id': str(job.id),
                    'message': 'Экспорт завершен успешно!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Ошибка при экспорте контактов'
                })

        except Exception as e:
            logger.error(f"Ошибка экспорта контактов: {e}")
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})


def process_import_file(job_id, file, file_format, bitrix_token):
    """Обработка импорта контактов с использованием batch"""
    try:
        job = ImportExportJob.objects.get(id=job_id)
        job.status = ImportExportJob.STATUS_PROCESSING
        job.save()

        contact_service = ContactService(bitrix_token)

        handler = FileHandlerFactory.get_handler(file_format)
        records = handler.read_records(file)

        if not records:
            job.status = ImportExportJob.STATUS_FAILED
            job.error_message = "Файл не содержит валидных данных"
            job.save()
            return False

        job.total_records = len(records)
        job.save()

        batch_size = 50
        success_count = 0
        fail_count = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            results = contact_service.batch_create_contacts(batch)

            for j, result in enumerate(results):
                record_index = i + j
                contact_data = batch[j] if j < len(batch) else {}

                ImportExportRecord.objects.create(
                    job=job,
                    record_index=record_index,
                    contact_data=contact_data,
                    status='success' if result.get('success') else 'failed',
                    error_message=str(result.get('error', ''))[:500],
                    bitrix_contact_id=result.get('contact_id')
                )

                if result.get('success'):
                    success_count += 1
                else:
                    fail_count += 1

            job.processed_records = min(i + batch_size, len(records))
            job.failed_records = fail_count
            job.save()

            time.sleep(0.5)

        job.status = ImportExportJob.STATUS_COMPLETED
        job.completed_at = timezone.now()
        job.save()

        logger.info(f"Импорт завершен: {success_count} успешно, {fail_count} с ошибками")
        return True

    except Exception as e:
        logger.error(f"Ошибка обработки импорта: {e}")
        if 'job' in locals():
            job.status = ImportExportJob.STATUS_FAILED
            job.error_message = str(e)
            job.save()
        return False


def process_export(job_id, filters, file_format, bitrix_token):
    """Обработка экспорта контактов с использованием batch"""
    try:
        job = ImportExportJob.objects.get(id=job_id)
        job.status = ImportExportJob.STATUS_PROCESSING
        job.save()

        contact_service = ContactService(bitrix_token)

        contacts = contact_service.get_contacts(filters)

        if not contacts:
            job.status = ImportExportJob.STATUS_COMPLETED
            job.total_records = 0
            job.processed_records = 0
            job.completed_at = timezone.now()
            job.save()
            return True

        job.total_records = len(contacts)
        job.save()

        contact_ids = [contact['ID'] for contact in contacts]
        company_names = contact_service.get_contact_companies(contact_ids)

        export_data = []
        for i, contact in enumerate(contacts):
            phone = ''
            if contact.get('PHONE'):
                phones = contact['PHONE']
                if isinstance(phones, list) and phones:
                    phone = phones[0].get('VALUE', '')
                elif isinstance(phones, dict):
                    phone = phones.get('VALUE', '')


            email = ''
            if contact.get('EMAIL'):
                emails = contact['EMAIL']
                if isinstance(emails, list) and emails:
                    email = emails[0].get('VALUE', '')
                elif isinstance(emails, dict):
                    email = emails.get('VALUE', '')

            company_name = company_names.get(contact['ID'], '')

            record_data = {
                'first_name': contact.get('NAME', ''),
                'last_name': contact.get('LAST_NAME', ''),
                'phone': phone,
                'email': email,
                'company_name': company_name
            }

            ImportExportRecord.objects.create(
                job=job,
                record_index=i,
                contact_data=record_data,
                status='exported',
                bitrix_contact_id=contact['ID']
            )

            export_data.append(record_data)
            job.processed_records = i + 1

            if (i + 1) % 50 == 0:
                job.save()

        job.save()

        handler = FileHandlerFactory.get_handler(file_format)
        response = handler.write_records(export_data)

        file_name = f"export_{job_id}.{file_format}"
        job.export_file.save(file_name, ContentFile(response.content))

        job.status = ImportExportJob.STATUS_COMPLETED
        job.completed_at = timezone.now()
        job.save()

        return True

    except Exception as e:
        logger.error(f"Ошибка обработки экспорта: {e}")
        job.status = ImportExportJob.STATUS_FAILED
        job.error_message = str(e)
        job.save()
        return False


@main_auth(on_cookies=True)
def download_export(request, job_id):
    """Скачивание экспортированного файла"""
    try:
        job = ImportExportJob.objects.get(
            id=job_id,
            created_by=request.bitrix_user,
            status=ImportExportJob.STATUS_COMPLETED,
            job_type=ImportExportJob.JOB_TYPE_EXPORT
        )

        if not job.export_file:
            return HttpResponse("Файл не найден", status=404)

        response = HttpResponse(job.export_file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{job.file_name}"'
        return response

    except ImportExportJob.DoesNotExist:
        return HttpResponse("Файл не найден или еще не готов", status=404)
    except Exception as e:
        logger.error(f"Ошибка скачивания файла: {e}")
        return HttpResponse("Ошибка при создании файла", status=500)


@main_auth(on_cookies=True)
def get_job_status(request, job_id):
    """Получение статуса задачи"""
    try:
        job = ImportExportJob.objects.get(id=job_id, created_by=request.bitrix_user)

        return JsonResponse({
            'success': True,
            'status': job.status,
            'total_records': job.total_records,
            'processed_records': job.processed_records,
            'failed_records': job.failed_records,
            'error_message': job.error_message
        })

    except ImportExportJob.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Задача не найдена'})


@main_auth(on_cookies=True)
def contacts_history(request):
    """Получение истории операций импорта/экспорта"""
    try:
        jobs = ImportExportJob.objects.filter(
            created_by=request.bitrix_user
        ).order_by('-created_at')[:20]

        history_data = []
        for job in jobs:
            history_data.append({
                'id': str(job.id),
                'job_type': job.job_type,
                'type_display': job.get_job_type_display(),
                'format': job.file_format,
                'status': job.status,
                'status_display': job.get_status_display(),
                'total_records': job.total_records,
                'processed_records': job.processed_records,
                'failed_records': job.failed_records,
                'created_at': job.created_at.isoformat(),
                'file_name': job.file_name
            })

        return JsonResponse(history_data, safe=False)

    except Exception as e:
        logger.error(f"Ошибка получения истории: {e}")
        return JsonResponse([], safe=False)