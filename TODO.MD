- Demucs provjera da li je instaliran i da li je enviroment aktivan
- Demucs sakriti viška output

- Intel Quick Sync i Apple MLX akceleracija za ffmpeg

- Streamlit interfejs na kraju kad sve bude funkcionalno ali će CLI ostati / možda i TKinter se odradi
- Proba One EXE file da se vidi veličina kompletnog projekta.

- Debugging (sakrivanje executing funkcija) i da ih snimi u log.

- Detekcija ko ima 64 GB RAM-a
The -j flag allow to specify a number of parallel jobs (e.g. demucs -j 2 myfile.mp3). This will multiply by the same amount the RAM used so be careful!

- Direktno pozivanje iz programa
Assume that your command is `demucs --mp3 --two-stems vocals -n mdx_extra "track with space.mp3"`
The following codes are same as the command above:
import demucs.separate
demucs.separate.main(["--mp3", "--two-stems", "vocals", "-n", "mdx_extra", "track with space.mp3"])

# Or like this
import demucs.separate
import shlex
demucs.separate.main(shlex.split('--mp3 --two-stems vocals -n mdx_extra "track with space.mp3"'))
