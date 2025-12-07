from django.urls import path

from . import views

app_name = "overwatch"

urlpatterns = [
    path("", views.server_list, name="server_list"),
    path("servers/<int:pk>/", views.server_detail, name="server_detail"),
    path("servers/add/", views.server_create, name="server_create"),
    path("servers/<int:pk>/edit/", views.server_edit, name="server_edit"),
    path("servers/<int:pk>/delete/", views.server_delete, name="server_delete"),
    path("servers/<int:pk>/notes/add/", views.server_note_create, name="server_note_create"),
    path("dictionary/", views.dictionary_list, name="dictionary_list"),
    path("dictionary/add/", views.dictionary_create, name="dictionary_create"),
    path("dictionary/<int:pk>/edit/", views.dictionary_edit, name="dictionary_edit"),
    path("dictionary/<int:pk>/delete/", views.dictionary_delete, name="dictionary_delete"),
    path("tags/", views.tag_list, name="tag_list"),
    path("tags/add/", views.tag_create, name="tag_create"),
    path("tags/<int:pk>/edit/", views.tag_edit, name="tag_edit"),
    path("tags/<int:pk>/delete/", views.tag_delete, name="tag_delete"),
    path("categories/", views.category_list, name="category_list"),
    path("categories/add/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
]
