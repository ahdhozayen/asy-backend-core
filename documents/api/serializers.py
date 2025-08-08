from rest_framework import serializers
from documents.models import Document, DocumentAttachment, Signature
from users.models import User


class SignedBySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name", "email", "role"]
        read_only_fields = ["id", "role"]


class DocumentAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentAttachment
        fields = "__all__"
        read_only_fields = ["id", "created_at"]


class SignatureSerializer(serializers.ModelSerializer):
    signed_by = SignedBySerializer(read_only=True)

    class Meta:
        model = Signature
        fields = "__all__"
        read_only_fields = ["id", "signed_by", "signed_at"]


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by = SignedBySerializer(read_only=True)
    reviewed_by = SignedBySerializer(read_only=True)
    attachments = DocumentAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "uploaded_by"]


class ListDocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "priority",
            "department",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "title",
            "description",
            "priority",
            "department",
            "status",
            "created_at",
        ]


class DocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "description", "priority", "department", "comments"]


class DocumentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "status", "comments", "redirect_department", "reviewed_by"]
        read_only_fields = ["reviewed_by"]


class DocumentAttachmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentAttachment
        fields = ["file", "document", "original_name"]
        extra_kwargs = {"file": {"required": True}, "document": {"required": True}}


class SignatureCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Signature
        fields = ["attachment", "signature_data"]
        read_only_fields = ["signed_by", "signed_at"]
