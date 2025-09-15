from django.contrib import admin
from .models import Video
from .forms import VideoForm

# Register your models here.
class VideoAdmin(admin.ModelAdmin):
    form = VideoForm
    list_display = ('id', 'title', 'status', 'created_at', 'updated_at')
    search_fields = ('title', 'status')
    list_filter = ('status',)
    
    def save_model(self, request, obj, form, change):
        form.save(commit=True)

admin.site.register(Video, VideoAdmin)