# Installation de VOD Atelier

Après avoir extrait le dossier complet de l’application, double-clique sur **Installer.cmd**.

Ce fichier prépare Python 3.12 x64, les bibliothèques, FFmpeg et FFprobe, le composant graphique Microsoft WebView2 si nécessaire, puis crée **VOD Atelier.exe**. Il installe ensuite Whisper, Ollama, Gemma et Qwen. Prévois plusieurs Go de téléchargement et d’espace disque pour les IA. Internet est nécessaire pendant l’installation.

Ouvre ensuite **VOD Atelier.exe** à la racine de l’application : l’interface apparaît dans sa propre fenêtre Windows, sans onglet de navigateur ni console. Les boutons **Parcourir**, **Choisir** et **Ouvrir un projet existant** utilisent les boîtes de dialogue Windows.

Les outils locaux sont rangés dans `tools`, les bibliothèques dans `.venv` et les modèles dans `models`. Le PATH Windows n’est pas modifié. Python/FFmpeg déjà utilisables sont conservés. Relancer l’installation reprend les étapes incomplètes ; les vidéos et projets ne sont pas effacés. WebView2 peut être installé pour l’utilisateur ou géré par Microsoft Edge selon le PC.

Garde l’EXE avec tous les fichiers du dossier. Copier uniquement l’EXE sur un autre PC ne suffit pas : copie le programme complet (ou télécharge le ZIP GitHub) et relance `Installer.cmd` sur ce PC pour préparer son environnement.

Pour installer les outils et la fenêtre sans télécharger les modèles immédiatement, lance `Installer.cmd -Mode Application`. Le bouton **Préparer l’IA** de l’application les installera ensuite. Pour recréer seulement l’EXE, utilise `..\.venv\Scripts\python.exe ..\build_desktop.py` depuis ce dossier.

En cas d’échec, consulte `installation.log` dans ce dossier et `application-desktop.log` à la racine.

Sources : [Python pour Windows / NuGet](https://docs.python.org/3.12/using/windows.html#the-nuget-org-packages), [FFmpeg / builds Windows](https://ffmpeg.org/download.html), [builds Gyan](https://www.gyan.dev/ffmpeg/builds/), [Microsoft WebView2](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution), [pywebview](https://pywebview.flowrl.com/guide/installation.html).
