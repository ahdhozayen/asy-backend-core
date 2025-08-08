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
        
        # Get counts by status
        status_counts = queryset.values('status').annotate(count=Count('id'))
        
        # Get counts by priority
        priority_counts = queryset.values('priority').annotate(count=Count('id'))
        
        # Get counts by department
        department_counts = queryset.values('department').annotate(count=Count('id'))
        
        return Response({
            'total_documents': queryset.count(),
            'by_status': {item['status']: item['count'] for item in status_counts},
            'by_priority': {item['priority']: item['count'] for item in priority_counts},
            'by_department': {item['department']: item['count'] for item in department_counts},
        })
