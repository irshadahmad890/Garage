from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from apps.user.models import User

from .models import JobMechanic, Mechanic, Specialization


class SpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialization
        fields = ['id', 'name', 'description', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Name cannot be empty.")
        existing = Specialization.objects.filter(name__iexact=value)
        if self.instance:
            existing = existing.exclude(id=self.instance.id)
        if existing.exists():
            raise serializers.ValidationError("Specialization already exists.")
        return value


class MechanicCreateSerializer(serializers.ModelSerializer):
    """Admin creates the login account and the mechanic profile together."""
    username = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    phone = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=15)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Mechanic
        fields = ['id', 'user', 'user_email', 'username', 'email', 'phone', 'password', 'specialization', 'name',
                  'experience_level', 'hourly_rate', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'user_email', 'created_at', 'updated_at']

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_phone(self, value):
        value = (value or "").strip() or None
        if value and User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("Phone already exists.")
        return value

    def validate_specialization(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This specialization is inactive.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        username = validated_data.pop('username')
        email = validated_data.pop('email')
        phone = validated_data.pop('phone', None)
        password = validated_data.pop('password')
        user = User.objects.create_user(username=username, email=email, password=password,
                                        phone=phone, role='mechanic')
        return Mechanic.objects.create(user=user, **validated_data)


class MechanicSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Mechanic
        fields = ['id', 'user', 'user_email', 'specialization', 'name', 'experience_level', 'hourly_rate',
                  'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user', 'user_email', 'created_at', 'updated_at']

    def validate_specialization(self, value):
        if not value.is_active:
            raise serializers.ValidationError("This specialization is inactive.")
        return value


class JobMechanicSerializer(serializers.ModelSerializer):
    """Admin. hourly_rate is read-only: it is copied from the mechanic when the assignment is created."""
    mechanic_name = serializers.CharField(source='mechanic.name', read_only=True)

    class Meta:
        model = JobMechanic
        fields = ['id', 'job', 'mechanic', 'mechanic_name', 'working_hours', 'hourly_rate', 'assigned_at']
        read_only_fields = ['id', 'hourly_rate', 'assigned_at']

    def validate(self, attrs):
        if self.instance:
            if 'job' in attrs and attrs['job'] != self.instance.job:
                raise serializers.ValidationError("You cannot change the assigned job.")
            if 'mechanic' in attrs and attrs['mechanic'] != self.instance.mechanic:
                raise serializers.ValidationError("You cannot change the assigned mechanic.")
        elif not attrs['mechanic'].is_active:
            raise serializers.ValidationError({'mechanic': "This mechanic is inactive."})
        return attrs   # a duplicate (job, mechanic) is rejected by the unique constraint validator

    def create(self, validated_data):
        validated_data['hourly_rate'] = validated_data['mechanic'].hourly_rate   # snapshot
        return super().create(validated_data)


class JobMechanicHoursSerializer(JobMechanicSerializer):
    """Mechanic. The ONLY writable field is working_hours."""

    class Meta(JobMechanicSerializer.Meta):
        read_only_fields = ['id', 'job', 'mechanic', 'hourly_rate', 'assigned_at']
