from django.urls import path
from rest_framework.urlpatterns import format_suffix_patterns
from . import views


app_name = "home"
urlpatterns = [
    # Stats URL
    path(
        "stats",
        views.DocumentStatsViewSet.as_view({"get": "list"}),
        name="document-stats",
    ),
]
