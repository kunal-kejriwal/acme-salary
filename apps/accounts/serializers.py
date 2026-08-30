"""Serializers for the auth endpoints."""

from django.contrib.auth import get_user_model
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    """Credentials only. Shape validation, never authentication."""

    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        # Passwords may legitimately begin or end with a space.
        trim_whitespace=False,
    )


class UserSerializer(serializers.ModelSerializer):
    """What the SPA is told about who it is signed in as."""

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "email", "first_name", "last_name", "is_staff"]
        read_only_fields = fields
