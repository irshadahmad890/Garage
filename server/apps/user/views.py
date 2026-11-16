from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializer import (
    ChangePasswordSerializer,
    CustomTokenSerializer,
    LogoutSerializer,
    RegisterSerializer,
    UserSerializer,
)

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]   # NEW: stops spam sign-ups
    throttle_scope = "register"

class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenSerializer
    throttle_classes = [ScopedRateThrottle]   # NEW: slows down password guessing
    throttle_scope = "login"


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET and PATCH /me/ (NEW: PATCH, and the hand-made dict is now a serializer)."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password"

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        # every old refresh token stops working
        for token in OutstandingToken.objects.filter(user=request.user):
            BlacklistedToken.objects.get_or_create(token=token)
        return Response({'detail': "Password changed. Please log in again."})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_205_RESET_CONTENT)
