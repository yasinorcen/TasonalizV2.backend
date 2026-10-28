"""
Views for user registration, JWT login, token refresh, and current user profile.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import RegisterSerializer, UserProfileSerializer


def get_tokens_for_user(user: User) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


class AuthBurstThrottle(ScopedRateThrottle):
    scope = "auth_burst"


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstThrottle]
    throttle_scope = "auth_burst"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Hesabınız başarıyla oluşturuldu.",
                "user": UserProfileSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [AuthBurstThrottle]
    throttle_scope = "auth_burst"

    def post(self, request):
        identifier = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))

        if not identifier or not password:
            return Response(
                {"detail": "Kullanıcı adı (veya e-posta) ve parola zorunludur."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        username = identifier
        if "@" in identifier:
            matched_user = User.objects.filter(email__iexact=identifier).first()
            if matched_user:
                username = matched_user.username

        user = authenticate(request=request, username=username, password=password)
        if user is None or not user.is_active:
            return Response(
                {"detail": "Kullanıcı adı veya parola hatalı."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        tokens = get_tokens_for_user(user)
        return Response(
            {
                "message": "Giriş başarılı.",
                "user": UserProfileSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK,
        )


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data)
