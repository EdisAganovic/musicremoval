Check for FFMPEG_EXE files and download them.

5. Creating final video...
   Output video file: nomusic\nomusic_What is Pizza Dough Hydration ｜ In-Depth Explanation Next Level.mp4

Executing: C:\Users\User\Desktop\musicremoval\backend\modules\ffmpeg.exe -loglevel error -y -i download\What is Pizza Dough Hydration ｜ In-Depth Explanation Next Level.webm -i C:\Users\User\Desktop\musicremoval_temp\tmpl7l9lp03.aac -vf scale=1920:1080 -c:v copy -c:a aac -b:a 192k -map 0:v:0 -map 1:a:0 -shortest -f mp4 nomusic\nomusic_What is Pizza Dough Hydration ｜ In-Depth Explanation Next Level.mp4
Filtergraph 'scale=1920:1080' was defined for video output stream 0:0 but codec copy was selected.
Filtering and streamcopy cannot be used together.
✖Error creating final output: Command '['C:\\Users\\User\\Desktop\\musicremoval\\backend\\modules\\ffmpeg.exe', '-loglevel', 'error', '-y', '-i', 'download\\What is Pizza Dough Hydration ｜ In-Depth Explanation Next Level.webm', '-i', 'C:\\Users\\User\\Desktop\\musicremoval\\_temp\\tmpl7l9lp03.aac', '-vf', 'scale=1920:1080', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-map', '0:v:0', '-map', '1:a:0', '-shortest', '-f', 'mp4', 'nomusic\\nomusic_What is Pizza Dough Hydration ｜ In-Depth Explanation Next Level.mp4']' returned non-zero exit status 1.
