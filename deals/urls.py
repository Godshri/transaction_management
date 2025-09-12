from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_initial, name='index_initial'),
    path('home/', views.index, name='index'),
    path('deals/', views.user_deals, name='deals'),
    path('create-deal/', views.create_deal, name='create_deal'),
]