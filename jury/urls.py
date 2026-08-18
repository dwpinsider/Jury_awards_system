from django.urls import path
from . import views

app_name = 'jury'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('categories/', views.category_list, name='category_list'),
    path('search/', views.search_nominations, name='search'),
    path('categories/<slug:slug>/', views.nomination_list, name='nomination_list'),
    path('nomination/<int:pk>/', views.nomination_detail, name='nomination_detail'),
    path('nomination/<int:pk>/review/', views.submit_review, name='submit_review'),
    path('my-reviews/', views.my_reviews, name='my_reviews'),
]