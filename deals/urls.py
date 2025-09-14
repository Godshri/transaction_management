from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_initial, name='index_initial'),
    path('home/', views.index, name='index'),
    path('deals/', views.user_deals, name='deals'),
    path('create-deal/', views.create_deal, name='create_deal'),
    path('generate-qr/', views.generate_qr, name='generate_qr'),
    path('product/<uuid:uuid>/', views.product_qr_detail, name='product_qr_detail'),
    path('api/search-products/', views.search_products, name='search_products'),
]