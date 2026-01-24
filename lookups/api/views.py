from rest_framework import viewsets, status
from rest_framework.response import Response
from lookups.models import Department, Priority
from lookups.api.serializers import DepartmentSerializer, PrioritySerializer


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        return Department.objects.filter(is_active=True)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        # If pagination is disabled, still return in standard format
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'next': None,
            'previous': None,
            'results': serializer.data
        })
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            self.perform_create(serializer)
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
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            'count': 1,
            'next': None,
            'previous': None,
            'results': [serializer.data]
        })
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        if serializer.is_valid():
            self.perform_update(serializer)
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
    
    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            self.perform_update(serializer)
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
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance_id = instance.id
        self.perform_destroy(instance)
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'message': f'Department with ID {instance_id} was successfully deleted'
        }, status=status.HTTP_200_OK)

class PriorityViewSet(viewsets.ModelViewSet):
    queryset = Priority.objects.all()
    serializer_class = PrioritySerializer

    def get_queryset(self):
        return Priority.objects.filter(is_active=True)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        # If pagination is disabled, still return in standard format
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'next': None,
            'previous': None,
            'results': serializer.data
        })