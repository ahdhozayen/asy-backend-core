from django.urls import path
from lookups.api import views

urlpatterns = [
    path(
        "departments",
        views.DepartmentViewSet.as_view({"get": "list"}),
        name="department-list",
    ),
    path(
        "departments/<int:pk>/",
        views.DepartmentViewSet.as_view({"get": "retrieve"}),
        name="department-detail",
    ),
]
