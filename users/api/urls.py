from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("user", views.UserViewSet, basename="user")

urlpatterns = [
    path("", include(router.urls)),
    # path("auth/login", views.LoginView.as_view({"post": "create"}), name="login"),
    path("auth/logout", views.LogoutView.as_view(), name="logout"),
    path(
        "auth/profile", views.ProfileView.as_view({"get": "list"}), name="get-profile"
    ),
    path(
        "auth/profile/update",
        views.ProfileView.as_view({"put": "update"}),
        name="update-profile",
    ),
    path(
        "auth/change-password",
        views.ChangePasswordView.as_view(),
        name="change-password",
    ),
]
