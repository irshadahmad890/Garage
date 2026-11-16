from rest_framework import serializers

from apps.customers.models import Customer
from apps.user.models import Role

from .models import Vehicle, normalize_plate


class VehicleBaseSerializer(serializers.ModelSerializer):
    # declared by hand so we can clean the value BEFORE the unique check
    registration_number = serializers.CharField(max_length=20)
    vin = serializers.CharField(max_length=17, required=False, allow_blank=True, allow_null=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = Vehicle
        fields = ['id', 'customer', 'customer_name', 'make', 'model', 'year', 'registration_number',
                  'vin', 'odometer_km', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def _is_admin(self):
        return self.context['request'].user.role == Role.ADMIN

    def _unique(self, field, value, message):
        qs = Vehicle.objects.filter(**{field: value})
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(message)

    def validate_registration_number(self, value):
        value = normalize_plate(value)
        if len(value) < 3:
            raise serializers.ValidationError("Enter a valid registration number.")
        if self.instance and not self._is_admin() and value != self.instance.registration_number:
            raise serializers.ValidationError("Please ask the garage to change the registration number.")
        self._unique('registration_number', value, "A vehicle with this registration number already exists.")
        return value

    def validate_vin(self, value):
        value = (value or "").strip().upper() or None
        if self.instance and not self._is_admin() and value != self.instance.vin:
            raise serializers.ValidationError("Please ask the garage to change the VIN.")
        if value:
            self._unique('vin', value, "A vehicle with this VIN already exists.")
        return value


class VehicleAdminSerializer(VehicleBaseSerializer):
    """Admin (and read-only mechanic). The admin chooses the customer."""
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.filter(is_active=True))


class VehicleCustomerSerializer(VehicleBaseSerializer):
    """Customer. `customer` is read-only: the view sets it from the login, never from the request.
    FIX: this also removes the dropdown that listed every customer in the browsable API."""

    class Meta(VehicleBaseSerializer.Meta):
        read_only_fields = VehicleBaseSerializer.Meta.read_only_fields + ['customer']
