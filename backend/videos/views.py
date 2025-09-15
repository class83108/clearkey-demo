from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Video

def video_list(request):
    videos = Video.objects.filter(status='READY').order_by('-created_at')
    return render(request, 'videos/video_list.html', {'videos': videos})

def video_detail(request, video_id):
    video = get_object_or_404(Video, id=video_id, status='READY')
    return render(request, 'videos/video_detail.html', {'video': video})

def license_api(request, video_id):
    video = get_object_or_404(Video, id=video_id, status='READY')
    
    # Convert hex to base64url for ClearKey
    import base64
    
    def hex_to_base64url(hex_str):
        # Convert hex to bytes, then to base64url
        bytes_data = bytes.fromhex(hex_str)
        b64 = base64.b64encode(bytes_data).decode('ascii')
        # Convert to base64url (replace +/= with -_)
        return b64.replace('+', '-').replace('/', '_').rstrip('=')
    
    kid_b64url = hex_to_base64url(video.kid_hex)
    key_b64url = hex_to_base64url(video.key_hex)
    
    # ClearKey license response
    keys = [{
        "kty": "oct",
        "kid": kid_b64url,
        "k": key_b64url
    }]
    
    return JsonResponse({"keys": keys})
