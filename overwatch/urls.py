from django.urls import path

from . import views

app_name = "overwatch"

urlpatterns = [
    path("", views.server_list, name="server_list"),
    path("servers/<int:pk>/", views.server_detail, name="server_detail"),
    path("dictionary/", views.dictionary_list, name="dictionary_list"),
    path("dictionary/add/", views.dictionary_create, name="dictionary_create"),
    path("dictionary/<int:pk>/edit/", views.dictionary_edit, name="dictionary_edit"),
    path("dictionary/<int:pk>/delete/", views.dictionary_delete, name="dictionary_delete"),
]
