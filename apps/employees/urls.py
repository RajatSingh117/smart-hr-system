from django.urls import path

from . import views

app_name = 'employees'

urlpatterns = [
    # Employee Routes
    path('', views.employee_list, name='employee_list'),
    path('list/', views.employee_list, name='list'),
    path('create/', views.employee_create, name='employee_create'),
    path('create/', views.employee_create, name='create'),
    path('<int:pk>/', views.employee_detail, name='employee_detail'),
    path('<int:pk>/', views.employee_detail, name='detail'),
    path('<int:pk>/edit/', views.employee_edit, name='employee_edit'),
    path('<int:pk>/edit/', views.employee_edit, name='edit'),

    # Department Routes
    path('departments/', views.department_list, name='department_list'),
    path('departments/list/', views.department_list, name='departments'),
    path('departments/create/', views.department_create, name='department_create'),
    path('departments/<int:pk>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:pk>/delete/', views.department_delete, name='department_delete'),
]
