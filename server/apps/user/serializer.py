from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.customers.models import Customer

from .models import User


class CustomTokenSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['role'] = user.role
        return token

    def validate(self, attrs):
        # FIX: emails are stored in lower case, so the login must not care about capital letters.
        attrs[self.username_field] = attrs[self.username_field].strip().lower()
        return super().validate(attrs)


class RegisterSerializer(serializers.ModelSerializer):
    """Public registration. Creates the user AND the customer profile in one transaction."""

    password = serializers.CharField(write_only=True, validators=[validate_password])  # FIX: was no validation
    name = serializers.CharField(write_only=True, max_length=100)                       # NEW: customer name
    address = serializers.CharField(write_only=True, required=False, allow_blank=True)  # NEW

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone', 'name', 'address', 'role']
        read_only_fields = ['id', 'role']   # the role can never come from the client

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_phone(self, value):
        return (value or "").strip() or None

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("Enter your full name.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        name = validated_data.pop('name')
        address = validated_data.pop('address', '')
        user = User.objects.create_user(**validated_data, role='customer')
        Customer.objects.create(user=user, name=name, phone=user.phone or '', address=address)
        return user


class UserSerializer(serializers.ModelSerializer):
    """GET /me/ and PATCH /me/. A user can edit only these personal fields."""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'first_name', 'last_name', 'role']
        read_only_fields = ['id', 'username', 'email', 'role']

    def validate_phone(self, value):
        return (value or "").strip() or None


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_old_password(self, value):
        if not self.context['request'].user.check_password(value):
            raise serializers.ValidationError("The old password is wrong.")
        return value

    def validate(self, attrs):
        validate_password(attrs['new_password'], self.context['request'].user)
        if attrs['new_password'] == attrs['old_password']:
            raise serializers.ValidationError({'new_password': "The new password must be different."})
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def save(self, **kwargs):
        try:
            RefreshToken(self.validated_data['refresh']).blacklist()
        except TokenError:
            raise serializers.ValidationError({'refresh': "This token is not valid."})
