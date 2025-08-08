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
    ]


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
        "signature_data",
        "signed_at",
    ]
