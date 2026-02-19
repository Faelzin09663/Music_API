import yt_dlp


def search_audio(query):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
        'geobypass': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)

            if 'entries' in info:
                video_data = info['entries'][0]
            else:
                video_data = info

            return {
                'title': video_data.get('title'),
                'url': video_data.get('url'),
                'duration': video_data.get('duration'),
                'thumbnail': video_data.get('thumbnail'),
                'uploader': video_data.get('uploader'),
            }

    except Exception as e:
        print(f"Error occurred: {e}")
        return None
