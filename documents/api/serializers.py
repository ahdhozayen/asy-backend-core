from datetime import datetime
from pathlib import Path
from rest_framework import serializers
from django.core.files.base import ContentFile
from documents.models import Document, DocumentAttachment, Signature
from users.models import User
from lookups.models import DefaultSignature


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
    priority_ar = serializers.CharField(source='priority.name_ar', read_only=True)
    priority_en = serializers.CharField(source='priority.name_en', read_only=True)
    department_ar = serializers.CharField(source='department.name_ar', read_only=True)
    department_en = serializers.CharField(source='department.name_en', read_only=True)

    class Meta:
        model = Document
        fields = "__all__"
        read_only_fields = ["id", "created_at", "updated_at", "uploaded_by"]


class ListDocumentSerializer(serializers.ModelSerializer):
    priority_ar = serializers.CharField(source='priority.name_ar', read_only=True)
    priority_en = serializers.CharField(source='priority.name_en', read_only=True)
    department_ar = serializers.CharField(source='department.name_ar', read_only=True)
    department_en = serializers.CharField(source='department.name_en', read_only=True)
    
    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "description",
            "priority",
            "priority_ar",
            "priority_en",
            "department_ar",
            "department_en",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "title",
            "description",
            "priority",
            "priority_ar",
            "priority_en",
            "department_ar",
            "department_en",
            "status",
            "created_at",
        ]


class DocumentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "description", "priority", "file_type", "comments"]


class DocumentUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ["id", "title", "description", "priority", "status", "comments", "redirect_department", "reviewed_by"]
        read_only_fields = ["reviewed_by"]


class DocumentAttachmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentAttachment
        fields = ["file", "document", "original_name"]
        extra_kwargs = {"file": {"required": True}, "document": {"required": True}}

    def validate(self, data):
        document = data.get('document')
        file_obj = data.get('file')

        if document and file_obj:
            file_name = file_obj.name.lower()
            file_type = document.file_type

            # Get file extension
            file_extension = Path(file_name).suffix.lower()

            # Validate PDF files
            if file_type == 'pdf':
                allowed_extensions = ['.pdf']
                allowed_mime_types = ['application/pdf']
                
                # Check file extension
                if file_extension not in allowed_extensions:
                    raise serializers.ValidationError(
                        f"Invalid file type. Only PDF files are allowed for this document type. "
                        f"Received file with extension: {file_extension}"
                    )
                
                # Additional validation: Check MIME type if available
                if hasattr(file_obj, 'content_type') and file_obj.content_type:
                    if file_obj.content_type not in allowed_mime_types:
                        raise serializers.ValidationError(
                            f"File MIME type '{file_obj.content_type}' does not match PDF format. "
                            f"Please upload a valid PDF file."
                        )
            
            # Validate Image files
            elif file_type == 'images':
                allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg']
                allowed_mime_types = [
                    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 
                    'image/bmp', 'image/webp', 'image/tiff', 'image/svg+xml'
                ]
                
                # Check file extension
                if file_extension not in allowed_extensions:
                    raise serializers.ValidationError(
                        f"Invalid file type. Only image files are allowed for this document type. "
                        f"Supported formats: {', '.join(allowed_extensions)}. "
                        f"Received file with extension: {file_extension}"
                    )
                
                # Additional validation: Check MIME type if available
                if hasattr(file_obj, 'content_type') and file_obj.content_type:
                    if file_obj.content_type not in allowed_mime_types:
                        raise serializers.ValidationError(
                            f"File MIME type '{file_obj.content_type}' does not match image format. "
                            f"Please upload a valid image file."
                        )

        return data

    def create(self, validated_data):
        """
        Create a DocumentAttachment with renamed file using integer timestamp.
        This prevents issues with Arabic or special characters in filenames.
        """
        file_obj = validated_data['file']
        original_name = validated_data.get('original_name', file_obj.name)
        
        # Get file extension from original file
        file_extension = Path(file_obj.name).suffix.lower()
        
        # Generate new filename using integer timestamp
        timestamp = int(datetime.now().timestamp())
        new_filename = f"{timestamp}{file_extension}"
        
        # Read file content and create new ContentFile with renamed filename
        file_content = file_obj.read()
        renamed_file = ContentFile(file_content, name=new_filename)
        
        # Replace the file in validated_data with the renamed file
        validated_data['file'] = renamed_file
        
        # Create and return the attachment
        return super().create(validated_data)


class SignatureCreateSerializer(serializers.ModelSerializer):
    signature_data = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    comments_data = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    department_data = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    is_approved = serializers.BooleanField(required=False, default=False)
    department_list = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = Signature
        fields = ["attachment", "signature_data", "comments_data", "department_data", "is_approved", "department_list"]
        read_only_fields = ["signed_by", "signed_at"]

    def validate(self, data):
        if data.get("is_approved"):
            data["signature_data"] = DefaultSignature.objects.get(id=1).signature_data
        return data

