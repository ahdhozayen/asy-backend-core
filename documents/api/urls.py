from django.urls import path
from . import views

document_detail = views.DocumentViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

document_status = views.DocumentViewSet.as_view({"post": "change_status"})

attachment_detail = views.DocumentAttachmentViewSet.as_view(
    {"get": "retrieve", "put": "update", "patch": "partial_update", "delete": "destroy"}
)

urlpatterns = [
    # Document URLs
    path(
        "list",
        views.DocumentViewSet.as_view({"get": "list"}),
        name="documents-list",
    ),
    path(
        "create",
        views.DocumentViewSet.as_view({"post": "create"}),
        name="document-create",
    ),
    path("<int:pk>", document_detail, name="document-detail"),
    path("<int:pk>/change-status", document_status, name="document-status"),
    # Document Attachment URLs
    path(
        "attachments/list",
        views.DocumentAttachmentViewSet.as_view({"get": "list"}),
        name="attachment-list",
    ),
    path(
        "attachments/create",
        views.DocumentAttachmentViewSet.as_view({"post": "create"}),
        name="attachment-create",
    ),
    path("attachments/<int:pk>", attachment_detail, name="attachment-detail"),
    # Signature URLs
    path(
        "signature/list",
        views.SignatureViewSet.as_view({"get": "list"}),
        name="signature-list",
    ),
    path(
        "signature/create",
        views.SignatureViewSet.as_view({"post": "create"}),
        name="signature-create",
    ),
    path(
        "signature/<int:pk>",
        views.SignatureViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="signature-detail",
    ),
]
