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

            # Получаем информацию о товаре
            product_result = token.call_api_method('crm.product.get', {
                'id': product_id_int
            })

            if 'result' not in product_result:
                return HttpResponseBadRequest("Товар не найден")

            product = product_result['result']
            product_name = product.get('NAME', 'Неизвестный товар')

            # Обрабатываем изображения товара
            images = []

            # Обрабатываем поле PROPERTY_44 (основные изображения)
            property_44 = product.get('PROPERTY_44')
            if property_44 and isinstance(property_44, list):
                for i, img_data in enumerate(property_44):
                    if isinstance(img_data, dict) and 'value' in img_data:
                        value_data = img_data['value']
                        if isinstance(value_data, dict):
                            # Используем downloadUrl - он содержит правильную ссылку
                            download_url = value_data.get('downloadUrl')
                            if download_url:
                                # Преобразуем относительный URL в абсолютный
                                if not download_url.startswith(('http://', 'https://')):
                                    download_url = f"https://b24-oyi9l4.bitrix24.ru{download_url}"

                                images.append({
                                    'id': f'image_{i}',
                                    'src': download_url,
                                    'title': f'Изображение {i + 1}'
                                })

            # Также проверяем другие возможные поля с изображениями
            other_image_fields = ['PREVIEW_PICTURE', 'DETAIL_PICTURE', 'MORE_PHOTO']
            for field in other_image_fields:
                field_value = product.get(field)
                if field_value:
                    # Аналогичная обработка для других полей
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
                        # Одиночное изображение
                        download_url = field_value.get('downloadUrl')
                        if download_url:
                            if not download_url.startswith(('http://', 'https://')):
                                download_url = f"https://b24-oyi9l4.bitrix24.ru{download_url}"

                            images.append({
                                'id': field,
                                'src': download_url,
                                'title': field.replace('_', ' ').title()
                            })

            # Сохраняем данные товара
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

        # Функция для преобразования ID изображения в URL
        def get_image_url(image_id):
            if not image_id:
                return None
            # Преобразуем ID в URL для изображения Битрикс24
            return f"https://b24-oyi9l4.bitrix24.ru/bitrix/components/bitrix/main.show/templates/.default/images/no_photo.png?{image_id}"

        # Преобразуем ID изображений в абсолютные URL
        for img in product_images:
            if 'src' in img and img['src']:
                # Если это уже URL, оставляем как есть
                if isinstance(img['src'], str) and img['src'].startswith(('http://', 'https://')):
                    continue
                # Если это ID изображения, преобразуем в URL
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

        # Ищем товары по названию с получением поля PROPERTY_44
        products_result = token.call_api_method('crm.product.list', {
            'filter': {'%NAME': query},
            'select': ['ID', 'NAME', 'PRICE', 'DESCRIPTION', 'PREVIEW_PICTURE', 'PROPERTY_44'],
            'order': {'NAME': 'ASC'},
            'start': 0
        })

        products = products_result.get('result', [])

        results = []
        for product in products[:10]:
            # Получаем первое изображение из PROPERTY_44 если есть
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

        # Получаем полную информацию о товаре
        product_result = token.call_api_method('crm.product.get', {
            'id': int(product_id)
        })

        if 'result' not in product_result:
            return JsonResponse({'success': False, 'error': 'Товар не найден'})

        product = product_result['result']

        # Обрабатываем изображение
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