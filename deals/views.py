from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from integration_utils.bitrix24.bitrix_user_auth.main_auth import main_auth
from integration_utils.bitrix24.bitrix_user_auth.authenticate_on_start_application import \
    authenticate_on_start_application
from integration_utils.bitrix24.bitrix_user_auth.get_bitrix_user_token_from_cookie import \
    get_bitrix_user_token_from_cookie, EmptyCookie


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
        return render(request, 'deals/welcome.html')


@main_auth(on_cookies=True)
def index(request):
    """Главная страница с аутентификацией через куки"""
    try:
        user = request.bitrix_user
        return render(request, 'deals/index.html', {
            'user_name': f"{user.first_name} {user.last_name}".strip() or user.email
        })
    except Exception as e:
        # Если куки устарели или нет аутентификации
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
            'select': ['ID', 'TITLE', 'STAGE_ID', 'OPPORTUNITY', 'DATE_CREATE', 'UF_CRM_CUSTOM_PRIORITY'],
            'order': {'DATE_CREATE': 'DESC'},
            'start': 0
        }).get('result', [])

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

            result = token.call_api_method('crm.deal.add', {
                'fields': {
                    'TITLE': title,
                    'OPPORTUNITY': opportunity,
                    'ASSIGNED_BY_ID': request.bitrix_user.bitrix_id,
                    'UF_CRM_CUSTOM_PRIORITY': custom_priority,
                    'COMMENTS': description,
                    'CATEGORY_ID': 0
                }
            })

            return redirect('deals')

        return render(request, 'deals/create_deal.html')
    except Exception as e:
        return HttpResponse(f"Ошибка при создании сделки: {str(e)}", status=500)