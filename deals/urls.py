from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.index_initial, name='index_initial'),
    path('home/', views.index, name='index'),
    path('deals/', views.user_deals, name='deals'),
    path('create-deal/', views.create_deal, name='create_deal'),
    path('generate-qr/', views.generate_qr, name='generate_qr'),
    path('product/<uuid:uuid>/', views.product_qr_detail, name='product_qr_detail'),
    path('api/search-products/', views.search_products, name='search_products'),
    path('api/product-details/', views.get_product_details, name='get_product_details'),
    path('employees/', views.employees_table, name='employees_table'),
    path('api/generate-test-calls/', views.generate_test_calls, name='generate_test_calls'),
]