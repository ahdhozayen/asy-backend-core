from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from documents.models import Document



class DocumentStatsViewSet(viewsets.ViewSet):
    """
    API endpoint that provides statistics about documents.
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        from django.db.models import Count, Q
        
        user = request.user
        queryset = Document.objects.all()
        
        # Apply role-based filtering
        if user.role != 'ceo':
            queryset = queryset.filter(
                Q(uploaded_by=user) | 
                Q(reviewed_by=user) |
                Q(status='pending')
            )
        
        stats_data = {
            'total_documents': queryset.count(),
            'total_signed': queryset.filter(status='signed').count(),
            'total_pending': queryset.filter(status='pending').count(),
        }
        
        return Response({
            'count': 1,
            'next': None,
            'previous': None,
            'results': [stats_data]
        })
