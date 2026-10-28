"""
Serializers for user registration, login, and profile inspection.
Uses Django's built-in password validation and never exposes password hashes.
"""

import re
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "date_joined")
        read_only_fields = ("id", "username", "date_joined")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        max_length=128,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        max_length=128,
        style={"input_type": "password"},
    )
    email = serializers.EmailField(required=True, max_length=150)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password_confirm",
        )

    def validate_username(self, value):
        cleaned = value.strip()
        if len(cleaned) < 3 or len(cleaned) > 30:
            raise serializers.ValidationError(
                "Kullanıcı adı 3 ile 30 karakter arasında olmalıdır."
            )
        if not re.match(r"^[a-zA-Z0-9_.-]+$", cleaned):
            raise serializers.ValidationError(
                "Kullanıcı adı yalnızca harf, rakam ve _ . - karakterlerini içerebilir."
            )
        if User.objects.filter(username__iexact=cleaned).exists():
            raise serializers.ValidationError("Bu kullanıcı adı zaten kullanılıyor.")
        return cleaned

    def validate_email(self, value):
        cleaned = value.strip().lower()
        if User.objects.filter(email__iexact=cleaned).exists():
            raise serializers.ValidationError(
                "Bu e-posta adresi ile kayıtlı bir hesap zaten mevcut."
            )
        return cleaned

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Girilen parolalar birbiriyle eşleşmiyor."}
            )
        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm", None)
        password = validated_data.pop("password")
        user = User(
            username=validated_data["username"],
            email=validated_data["email"],
            first_name=validated_data.get("first_name", "").strip()[:50],
            last_name=validated_data.get("last_name", "").strip()[:50],
        )
        user.set_password(password)
        user.save()
        return user
