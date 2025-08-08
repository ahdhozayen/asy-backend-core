from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class Document(models.Model):
    PRIORITY_CHOICES = [
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('signed', 'Signed'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    priority = models.CharField(
        max_length=10, 
        choices=PRIORITY_CHOICES, 
        default='medium'
    )
    department = models.CharField(max_length=100)
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,
        related_name='uploaded_documents'
    )
    reviewed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True,
        related_name='reviewed_documents'
    )
    comments = models.TextField(blank=True, null=True)
    redirect_department = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"


class DocumentAttachment(models.Model):
    document = models.ForeignKey(
        Document, 
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    is_signed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Document Attachment'
        verbose_name_plural = 'Document Attachments'

    def __str__(self):
        return f"{self.original_name} ({self.document.title})"


class Signature(models.Model):
    attachment = models.ForeignKey(
        DocumentAttachment,
        on_delete=models.CASCADE,
        related_name='signatures'
    )
    signed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='signatures'
    )
    signature_data = models.TextField(help_text='Base64 encoded signature')
    signed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-signed_at']
        verbose_name = 'Signature'
        verbose_name_plural = 'Signatures'

    def __str__(self):
        return f"Signature by {self.signed_by.username} on {self.signed_at}"
