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
        queryset = Document.objects.all()
        
        # Filter based on user role
        if user.role == 'ceo':
            # CEO can see all documents
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
        document.delete()
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
        if hasattr(self, '_paginator'):
            if self.request.query_params.get('no_page', '').lower() != 'true':
                return self._paginator.paginate_queryset(queryset, self.request, view=self)
        return None
        
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
        serializer = SignatureCreateSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(signed_by=request.user)
            sign_doc = SignatureAgent(serializer.instance)
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

