import yt_dlp
from yt_dlp.networking.impersonate import ImpersonateTarget

ydl_opts = {
    'quiet': True,
    'noplaylist': True,
    'remote_components': ['ejs:github'],
    'impersonate': ImpersonateTarget(client='chrome')
}

url = "https://www.youtube.com/watch?v=sduaTkhIm_w"

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(url, download=False)
    for f in info.get('formats', []):
        fs = f.get('filesize')
        fsa = f.get('filesize_approx')
        id_ = f.get('format_id')
        if fs is not None or fsa is not None:
             print(f"ID={id_}, size={fs}, approx={fsa}")
        else:
             print(f"ID={id_}, NO SIZE AT ALL")
