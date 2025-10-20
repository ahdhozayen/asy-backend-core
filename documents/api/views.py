from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import csrf_exempt

from django_filters.rest_framework import DjangoFilterBackend

from documents.models import Document, DocumentAttachment, Signature
from .serializers import (
    ListDocumentSerializer,
    DocumentAttachmentCreateSerializer,
    DocumentAttachmentSerializer,
    DocumentCreateSerializer,
    DocumentSerializer,
    DocumentUpdateSerializer,
    SignatureCreateSerializer,
    SignatureSerializer,
)
from documents.services.sign_document import SignatureAgent
from ASY_CORE.pagination import StandardResultsSetPagination

class DocumentViewSet(viewsets.GenericViewSet):
    """
    API endpoint that allows documents to be viewed or edited.
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'department', 'uploaded_by', 'reviewed_by']
    search_fields = ['title', 'description', 'comments']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']
    pagination_class = StandardResultsSetPagination

    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DocumentUpdateSerializer
        elif self.action == 'list':
            return ListDocumentSerializer
        return DocumentSerializer
    
    def get_queryset(self):
        user = self.request.user
        # Exclude soft-deleted documents from all queries
        queryset = Document.objects.filter(is_deleted=False)

        # Filter based on user role
        if user.role == 'ceo':
            # CEO can see all documents (except deleted)
            return queryset
        else:
            # Helpdesk can see documents they uploaded or are assigned to review
            return queryset.filter(
                Q(uploaded_by=user) |
                Q(reviewed_by=user) |
                Q(status='pending')
            )
    
    def list(self, request):
        queryset = self.get_queryset()
        
        # Apply filters, search, and ordering
        for backend in list(self.filter_backends):
            queryset = backend().filter_queryset(request, queryset, self)
            
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer_class()(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        # If pagination is disabled, still return in standard format
        serializer = self.get_serializer_class()(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'next': None,
            'previous': None,
            'results': serializer.data
        })
    
    def create(self, request):
        serializer = DocumentCreateSerializer(data=request.data)
        if serializer.is_valid():
            document = serializer.save(uploaded_by=request.user)
            return Response({
                'count': 1,
                'next': None,
                'previous': None,
                'results': [serializer.data]
            }, status=status.HTTP_201_CREATED)
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def retrieve(self, request, pk=None):
        queryset = self.get_queryset()
        document = get_object_or_404(queryset, pk=pk)
        serializer = DocumentSerializer(document)
        return Response({
            'count': 1,
            'next': None,
            'previous': None,
            'results': [serializer.data]
        })
    
    def update(self, request, pk=None):
        queryset = self.get_queryset()
        document = get_object_or_404(queryset, pk=pk)
        serializer = DocumentUpdateSerializer(document, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'count': 1,
                'next': None,
                'previous': None,
                'results': [serializer.data]
            })
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def partial_update(self, request, pk=None):
        queryset = self.get_queryset()
        document = get_object_or_404(queryset, pk=pk)
        serializer = DocumentUpdateSerializer(document, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({
                'count': 1,
                'next': None,
                'previous': None,
                'results': [serializer.data]
            })
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, pk=None):
        queryset = self.get_queryset()
        document = get_object_or_404(queryset, pk=pk)
        document_id = document.id
        # Soft delete: set is_deleted flag instead of calling delete()
        document.is_deleted = True
        document.save()
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'message': f'Document with ID {document_id} was successfully deleted'
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def change_status(self, request, pk=None):
        queryset = self.get_queryset()
        document = get_object_or_404(queryset, pk=pk)
        new_status = request.data.get('status')
        
        if not new_status:
            return Response({
                'count': 0,
                'next': None,
                'previous': None,
                'results': [],
                'errors': {'status': 'Status is required'}
            }, status=status.HTTP_400_BAD_REQUEST)
        
        document.status = new_status
        
        # If status is being changed to 'in_review', set the reviewer
        if new_status == 'in_review' and not document.reviewed_by:
            document.reviewed_by = request.user
        
        document.save()
        serializer = self.get_serializer_class()(document)
        return Response({
            'count': 1,
            'next': None,
            'previous': None,
            'results': [serializer.data]
        })
        
    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)
        
    def paginate_queryset(self, queryset):
        """Initialize paginator and paginate queryset"""
        if not hasattr(self, '_paginator'):
            self._paginator = self.pagination_class()
            
        if self.request.query_params.get('no_page', '').lower() == 'true':
            return None
            
        return self._paginator.paginate_queryset(queryset, self.request, view=self)
        
    def get_paginated_response(self, data):
        assert hasattr(self, '_paginator')
        return self._paginator.get_paginated_response(data)


class DocumentAttachmentViewSet(viewsets.ViewSet):
    """
    API endpoint that allows document attachments to be managed.
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return DocumentAttachmentCreateSerializer
        return DocumentAttachmentSerializer
    
    def get_queryset(self):
        queryset = DocumentAttachment.objects.all()
        document_id = self.request.query_params.get('document_id')
        
        if document_id:
            queryset = queryset.filter(document_id=document_id)
            
        return queryset
    
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer_class()(queryset, many=True)
        return Response(serializer.data)
    
    @csrf_exempt
    def create(self, request):
        serializer = DocumentAttachmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def retrieve(self, request, pk=None):
        queryset = self.get_queryset()
        attachment = get_object_or_404(queryset, pk=pk)
        serializer = DocumentAttachmentSerializer(attachment)
        return Response(serializer.data)
    
    def update(self, request, pk=None):
        queryset = self.get_queryset()
        attachment = get_object_or_404(queryset, pk=pk)
        serializer = DocumentAttachmentSerializer(attachment, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def partial_update(self, request, pk=None):
        queryset = self.get_queryset()
        attachment = get_object_or_404(queryset, pk=pk)
        serializer = DocumentAttachmentSerializer(attachment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, pk=None):
        queryset = self.get_queryset()
        attachment = get_object_or_404(queryset, pk=pk)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)


class SignatureViewSet(viewsets.ViewSet):
    """
    API endpoint that manages document signatures.
    """
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SignatureCreateSerializer
        return SignatureSerializer
    
    def get_queryset(self):
        queryset = Signature.objects.all()
        attachment_id = self.request.query_params.get('attachment_id')
        
        if attachment_id:
            queryset = queryset.filter(attachment_id=attachment_id)
            
        return queryset
    
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer_class()(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request):
        import os
        import shutil
        from django.core.files import File

        data = request.data
        user_comments = data.pop("comments")
        print(data)
        serializer = SignatureCreateSerializer(data=data)
        if serializer.is_valid():
            attachment_id = serializer.validated_data.get('attachment')

            # Check if there are existing signatures for this attachment
            existing_signatures = Signature.objects.filter(attachment=attachment_id)

            if existing_signatures.exists():
                # VERSION REPLACEMENT LOGIC
                # 1. Get the attachment
                attachment = attachment_id

                # 2. If original_file doesn't exist, back up the current file first
                if not attachment.original_file:
                    # This is the first signature - back up the original
                    original_file_path = attachment.file.path
                    if os.path.exists(original_file_path):
                        # Copy the original file to original_file field
                        with open(original_file_path, 'rb') as f:
                            file_name = os.path.basename(original_file_path)
                            attachment.original_file.save(file_name, File(f), save=False)

                # 3. Restore the original file to the main file field
                if attachment.original_file:
                    original_path = attachment.original_file.path
                    current_path = attachment.file.path

                    if os.path.exists(original_path):
                        # Copy original back to current
                        shutil.copy2(original_path, current_path)

                # 4. Delete all existing signatures for this attachment
                existing_signatures.delete()

                # 5. Increment version number
                attachment.version_number += 1
                attachment.save()
            else:
                # FIRST SIGNATURE LOGIC
                # Back up the original file before first signature
                attachment = attachment_id
                if not attachment.original_file:
                    original_file_path = attachment.file.path
                    if os.path.exists(original_file_path):
                        with open(original_file_path, 'rb') as f:
                            file_name = os.path.basename(original_file_path)
                            attachment.original_file.save(file_name, File(f), save=False)
                        attachment.save()

            # Create the new signature
            signature_obj = serializer.save(signed_by=request.user)
            signature_obj.attachment.document.comments = user_comments
            signature_obj.attachment.document.save()

            # For image documents, increment version for ALL image attachments that will be processed
            document = signature_obj.attachment.document
            file_extension = os.path.splitext(signature_obj.attachment.file.name)[1].lower()
            if file_extension in ['.png', '.jpg', '.jpeg']:
                # This is an image document - all image attachments will be signed
                # Check if this is a re-signature by checking the main attachment
                main_attachment_version = signature_obj.attachment.version_number

                # If main attachment version > 1, this is a re-signature for all images
                if main_attachment_version > 1:
                    all_image_attachments = document.attachments.filter(
                        file__iregex=r'\.(png|jpg|jpeg)$'
                    ).exclude(id=signature_obj.attachment.id)

                    for attachment in all_image_attachments:
                        # Increment version for all other image attachments
                        attachment.version_number += 1
                        attachment.save()

            # Process the document with the new signature
            sign_doc = SignatureAgent(signature_obj)
            sign_doc.process_document()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def retrieve(self, request, pk=None):
        queryset = self.get_queryset()
        signature = get_object_or_404(queryset, pk=pk)
        serializer = SignatureSerializer(signature)
        return Response(serializer.data)
    
    def update(self, request, pk=None):
        queryset = self.get_queryset()
        signature = get_object_or_404(queryset, pk=pk)
        serializer = SignatureSerializer(signature, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def partial_update(self, request, pk=None):
        queryset = self.get_queryset()
        signature = get_object_or_404(queryset, pk=pk)
        serializer = SignatureSerializer(signature, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def destroy(self, request, pk=None):
        queryset = self.get_queryset()
        signature = get_object_or_404(queryset, pk=pk)
        signature.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    def get_serializer(self, *args, **kwargs):
        serializer_class = self.get_serializer_class()
        return serializer_class(*args, **kwargs)

