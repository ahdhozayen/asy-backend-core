from rest_framework import serializers
from lookups.models import Department, Priority


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            "id",
            "name_ar",
            "name_en",
        ]

class PrioritySerializer(serializers.ModelSerializer):
    class Meta:
        model = Priority
        fields = [
            "id",
            "name_ar",
            "name_en",
        ]