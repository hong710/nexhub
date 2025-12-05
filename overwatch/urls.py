from django.urls import path

from . import views

app_name = "overwatch"

urlpatterns = [
    path("", views.server_list, name="server_list"),
    path("servers/<int:pk>/", views.server_detail, name="server_detail"),
]
