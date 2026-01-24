from django.contrib import admin
from .models import Department, Priority, DefaultSignature

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name_ar', 'name_en')
    ordering = ('-created_at',)

@admin.register(Priority)
class PriorityAdmin(admin.ModelAdmin):
    list_display = ('name_ar', 'name_en', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name_ar', 'name_en')
    ordering = ('-created_at',)


@admin.register(DefaultSignature)
class DefaultSignatureAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    ordering = ('-created_at',)