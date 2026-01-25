from django.contrib import admin

from documents.models import Document, DocumentAttachment, Signature


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "description",
        "priority",
        "department",
        "status",
        "is_deleted",
        "created_at",
    ]
    list_filter = [
        "is_deleted",
        "status",
        "priority",
        "department",
        "created_at",
    ]
    search_fields = ["title", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DocumentAttachment)
class DocumentAttachmentAdmin(admin.ModelAdmin):
    list_display = [
        "document",
        "original_name",
        "created_at",
    ]


@admin.register(Signature)
class SignatureAdmin(admin.ModelAdmin):
    list_display = [
        "attachment",
        "signed_by",
        "comments_data",
        "is_approved",
        "department_list",
        "signed_at",
    ]
