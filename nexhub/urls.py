"""
nexhub URL Configuration

The `urlpatterns` list routes URLs to views.
"""

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from overwatch.views import CategoryViewSet, ServerViewSet, SubnetViewSet, TagViewSet, log_event


def logout_view(request):
    """Custom logout view that handles both GET and POST."""
    user = request.user
    if user.is_authenticated:
        log_event(user, "other", None, f"User {user.username} logged out")
    auth_logout(request)
    return redirect('login')


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
    
    # Authentication URLs
    path("login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", logout_view, name="logout"),
    
    path("", include("overwatch.urls")),
]
