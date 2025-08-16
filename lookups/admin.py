from django.contrib import admin
from .models import Department

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name_ar', 'name_en')
    ordering = ('-created_at',)

