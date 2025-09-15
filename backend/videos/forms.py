from django import forms
from .models import Video
from .tasks import encrypt_video
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

class VideoForm(forms.ModelForm):
    class Meta:
        model = Video
        fields = ['title', 'file']

    def save(self, commit=True):
        instance = super().save(commit=commit)
        print("***********commit: ", commit)
        # Ensure instance is saved and transaction committed before enqueuing
        if commit:
            def _enqueue():
                try:
                    encrypt_video.delay(instance.id)
                except Exception as e:
                    logger.exception("Failed to enqueue encrypt_video task: %s", e)

            transaction.on_commit(_enqueue)
        return instance
