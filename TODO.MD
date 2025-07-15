- Demucs provjera da li je instaliran i da li je enviroment aktivan
- Demucs sakriti viška output

  
- Separacija svih fajlova u jednom folderu (main.py folder download ili main.py folder d:\crtani)
+ Failback za libfdk_aac za ffmpeg
- Debugging (sakrivanje executing funkcija) i da ih snimi u log.

- Demucs probati druge modele
htdemucs: first version of Hybrid Transformer Demucs. Trained on MusDB + 800 songs. Default model.
htdemucs_ft: fine-tuned version of htdemucs, separation will take 4 times more time but might be a bit better. Same training set as htdemucs.
htdemucs_6s: 6 sources version of htdemucs, with piano and guitar being added as sources. Note that the piano source is not working great at the moment.
hdemucs_mmi: Hybrid Demucs v3, retrained on MusDB + 800 songs.
mdx: trained only on MusDB HQ, winning model on track A at the MDX challenge.
mdx_extra: trained with extra training data (including MusDB test set), ranked 2nd on the track B of the MDX challenge.
mdx_q, mdx_extra_q: quantized version of the previous models. Smaller download and storage but quality can be slightly worse.

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
