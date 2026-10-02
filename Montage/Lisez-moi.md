# Montage des épisodes

Place ces deux fichiers dans ce dossier, à côté de ce document :

- **Starting Screen.mp4** : l’écran animé de départ (au moins deux secondes), avec ou sans musique.
- **Stinger.webm** : la transition ; la transparence VP9 WebM est prise en charge.

Chaque vidéo commence par deux secondes de starting screen. Le stinger est ensuite superposé : le fond passe au premier écran du jeu quand le stinger couvre l’image. Ce premier écran reste figé pendant la révélation ; les paroles et le contenu complet du clip commencent après la transition. Le son du starting screen continue pendant l’intro et s’atténue sur ses 250 dernières millisecondes. Toutes les pistes audio du stream reprennent ensuite, sans retirer de passage. Le fondu au noir dure deux secondes à la fin ; les paroles ne sont pas atténuées.

Les fichiers de montage personnels restent sur le PC et ne sont pas publiés sur GitHub. Tu peux désactiver le montage dans l’application pour utiliser la copie sans réencodage.
