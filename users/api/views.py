from django.contrib.auth import authenticate, login, logout
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets

from users.models import User
from .serializers import UserRegisterSerializer, UserSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """Allow unauthenticated users to create accounts."""
        if self.action == "create":
            return [AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return UserRegisterSerializer
        return UserSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role == "ceo":
            return User.objects.all()
        return User.objects.filter(pk=user.pk)
        
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
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
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
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
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance_id = instance.id
        self.perform_destroy(instance)
        return Response({
            'count': 0,
            'next': None,
            'previous': None,
            'results': [],
            'message': f'User with id {instance_id} was deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)


# class LoginView(viewsets.GenericViewSet):
#     serializer_class = UserSerializer
#     permission_classes = [AllowAny]

#     def create(self, request):
#         username = request.data.get("username")
#         password = request.data.get("password")

#         if not username or not password:
#             return Response(
#                 {"error": "Please provide both username and password"},
#                 status=status.HTTP_400_BAD_REQUEST,
#             )

#         user = authenticate(request, username=username, password=password)

#         if user is not None:
#             if not user.is_active:
#                 return Response(
#                     {"error": "This account is disabled"},
#                     status=status.HTTP_401_UNAUTHORIZED,
#                 )

#             login(request, user)
#             token, created = Token.objects.get_or_create(user=user)

#             response_data = {"token": token.key, "user": UserSerializer(user).data}

#             response = Response(response_data)
#             return response

#         return Response(
#             {"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED
#         )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Delete the auth token if it exists
            if hasattr(request, "auth") and request.auth:
                request.auth.delete()

            # Logout the user
            logout(request)

            # Create a response and delete cookies
            response = Response({
                'count': 1,
                'next': None,
                'previous': None,
                'results': [{"message": "Successfully logged out."}]
            }, status=status.HTTP_200_OK)
            response.delete_cookie("sessionid")
            response.delete_cookie("csrftoken")

            return response
        except Exception as e:
            return Response({
                'count': 0,
                'next': None,
                'previous': None,
                'results': [],
                'errors': {"detail": str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProfileView(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def list(self, request):
        try:
            serializer = UserSerializer(request.user)
            return Response({
                'count': 1,
                'next': None,
                'previous': None,
                'results': [serializer.data]
            })
        except Exception as e:
            return Response({
                'count': 0,
                'next': None,
                'previous': None,
                'results': [],
                'errors': {'detail': str(e)}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, pk=None):
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            # Don't allow changing password through this endpoint
            if "password" in request.data:
                return Response({
                    'count': 0,
                    'next': None,
                    'previous': None,
                    'results': [],
                    'errors': {"password": "Use the change password endpoint to update password"}
                }, status=status.HTTP_400_BAD_REQUEST)

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


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response({
                'count': 0,
                'next': None,
                'previous': None,
                'results': [],
                'errors': {"error": "Both old and new password are required"}
            }, status=status.HTTP_400_BAD_REQUEST)

        if not user.check_password(old_password):
            return Response({
                'count': 0,
                'next': None,
                'previous': None,
                'results': [],
                'errors': {"error": "Incorrect old password"}
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        # Delete existing tokens to force re-login
        Token.objects.filter(user=user).delete()

        return Response({
            'count': 1,
            'next': None,
            'previous': None,
            'results': [{"message": "Password updated successfully"}]
        })
