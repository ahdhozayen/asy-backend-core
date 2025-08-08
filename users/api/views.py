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
            response = Response(
                {"detail": "Successfully logged out."}, status=status.HTTP_200_OK
            )
            response.delete_cookie("sessionid")
            response.delete_cookie("csrftoken")

            return response
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProfileView(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def list(self, request):
        try:
            serializer = UserSerializer(request.user)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def update(self, request, pk=None):
        user = request.user
        serializer = self.get_serializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            # Don't allow changing password through this endpoint
            if "password" in request.data:
                return Response(
                    {"password": "Use the change password endpoint to update password"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, format=None):
        user = request.user
        old_password = request.data.get("old_password")
        new_password = request.data.get("new_password")

        if not old_password or not new_password:
            return Response(
                {"error": "Both old and new password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user.check_password(old_password):
            return Response(
                {"error": "Incorrect old password"}, status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()

        # Delete existing tokens to force re-login
        Token.objects.filter(user=user).delete()

        return Response({"success": "Password updated successfully"})
