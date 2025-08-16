from rest_framework import serializers
from lookups.models import Department


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = [
            "id",
            "name_ar",
            "name_en",
        ]
