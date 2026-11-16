from rest_framework import serializers

from .models import JobPart, Part


class PartSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.SerializerMethodField()

    class Meta:
        model = Part
        fields = ['id', 'name', 'price', 'stock', 'reorder_level', 'is_low_stock', 'is_active',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_low_stock(self, obj):
        return obj.stock <= obj.reorder_level

    def validate_name(self, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Enter the part name.")
        return value


class JobPartSerializer(serializers.ModelSerializer):
    """FIX: unit_price is read-only. The server copies Part.price, so a client cannot set its own price."""
    part_name = serializers.CharField(source='part.name', read_only=True)
    line_total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = JobPart
        fields = ['id', 'job', 'part', 'part_name', 'quantity', 'unit_price', 'line_total']
        read_only_fields = ['id', 'unit_price']

    def validate(self, attrs):
        if self.instance:   # the line cannot be moved to another job or part: delete it and add a new one
            for field in ('job', 'part'):
                if field in attrs and attrs[field] != getattr(self.instance, field):
                    raise serializers.ValidationError({field: "This cannot be changed."})
        elif not attrs['part'].is_active:
            raise serializers.ValidationError({'part': "This part is not sold any more."})
        return attrs

    def create(self, validated_data):
        validated_data['unit_price'] = validated_data['part'].price   # snapshot
        return super().create(validated_data)
