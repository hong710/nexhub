"""
nexhub URL Configuration

The `urlpatterns` list routes URLs to views.
"""

from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from overwatch.views import CategoryViewSet, ServerViewSet, SubnetViewSet, TagViewSet

# API Router
router = DefaultRouter()
router.register(r"servers", ServerViewSet, basename="server")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"subnets", SubnetViewSet, basename="subnet")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api/auth/", include("rest_framework.urls")),
    path("", include("overwatch.urls")),
]
