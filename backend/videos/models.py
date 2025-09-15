from django.db import models

# Create your models here.
class Video(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='uploads/')
    status = models.CharField(max_length=20, choices=[
        ('uploading', 'Uploading'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('READY', 'READY'),
    ], default='processing')
    kid_hex = models.CharField(max_length=32, blank=True, null=True)
    key_hex = models.CharField(max_length=32, blank=True, null=True)
    encrypted_path = models.CharField(max_length=255, blank=True, null=True)
    enable_compression = models.BooleanField(default=False, help_text="Enable video compression before encryption")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
