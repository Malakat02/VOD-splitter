# VOD-splitter · VOD Atelier

Application Windows avec sa propre fenêtre pour transformer une longue VOD en épisodes.

## Installer depuis GitHub

Télécharge le dépôt avec **Code → Download ZIP**, puis extrais le ZIP, ou clone-le avec Git. Dans le dossier **Installation**, double-clique sur **Installer.cmd**. Il prépare Python 3.12 x64, les bibliothèques, FFmpeg/FFprobe, Microsoft WebView2 si nécessaire, puis crée **VOD Atelier.exe** et prépare les IA locales. Le dépôt contient le programme et son installateur, pas les modèles IA ni les vidéos.

Double-clique ensuite sur **VOD Atelier.exe**. Garde cet EXE avec les autres fichiers du dossier. Les outils sont préparés localement dans `tools`, `.venv` et `models`, sans ajouter de commandes au PATH Windows. Pour différer le téléchargement des modèles, utilise `Installation\Installer.cmd -Mode Application`, puis **Préparer l’IA** dans la fenêtre. Les détails figurent dans [Installation/Lisez-moi.md](Installation/Lisez-moi.md).

## Ouvrir l’application

Double-clique sur **VOD Atelier.exe** ou **Lancer VOD Atelier.cmd**. L’interface s’ouvre dans une fenêtre Windows avec son icône, sans navigateur ni console. Elle intègre l’interface existante grâce à Microsoft WebView2 ; le moteur interne écoute uniquement sur `127.0.0.1` et se ferme avec la fenêtre. Une demande de fermeture pendant un traitement propose de l’arrêter, attend sa fin et conserve les clips terminés. Les liens de documentation et de recherche peuvent ouvrir ton navigateur habituel.

1. Choisis ta vidéo avec **Parcourir**, ou colle son chemin. La version bureau ouvre le sélecteur de fichiers Windows. Le mode navigateur de développement conserve son sélecteur intégré.
2. Indique le début du contenu : `05:00` retire cinq minutes. La durée des épisodes commence après cette intro.
3. Garde **20 minutes**, ou choisis une autre durée. Les pauses de voix permettent des ajustements de ±30 secondes.
4. Ajoute tes fichiers au dossier **Montage** et garde **Ajouter mon montage** : écran de départ de deux secondes, stinger transparent et fondu au noir final de deux secondes. Le **montage partiel**, sélectionné par défaut, copie la vidéo centrale des VOD H.264 compatibles. Le montage complet reste disponible, ainsi que le rendu sans perte (MKV volumineux). Décoche le montage pour conserver la copie rapide sans réencodage.
5. Saisis le **nom exact du jeu** et le **numéro du premier clip**. Le jeu saisi fixe le périmètre de recherche et d’analyse : il ne doit pas être remplacé par un jeu supposé à partir de Whisper.
6. Garde **Rechercher le contexte du jeu sur Internet** pour utiliser des sources sur le jeu. Les liens consultés sont affichés. Seul le nom du jeu sert à la recherche ; aucune vidéo, image ou transcription n’est envoyée au moteur de recherche. En mode OpenAI, les résumés de cinq minutes et les huit images sont envoyés à OpenAI pour l’analyse ; la transcription détaillée reste locale.
7. Choisis **IA locale** ou **OpenAI**, puis coche **Analyser avec l’IA** pour obtenir les titres et la miniature choisie par le modèle.
8. Clique sur **Créer mes épisodes**.

Les résultats sont dans un nouveau sous-dossier de **Clips VOD**, à côté de la vidéo, sauf si tu choisis une autre destination. Le bouton **Choisir** ouvre le sélecteur de dossiers Windows. Les fichiers existants ne sont pas écrasés. Une heure de contenu utile donne environ trois épisodes de 20 minutes. Une VOD d’une heure dont on retire cinq minutes donne environ 20 + 35 minutes : le dernier morceau court est intégré au précédent.

## Contenu des résultats

- Dossiers **Clip 001**, **Clip 002**, etc. : chacun contient directement sa vidéo, sa miniature JPEG 1280 × 720, ses titres, les huit images candidates et la planche de contact. Avec un nom de jeu, la vidéo est renommée d’après le premier titre validé. Les anciens projets conservent leur organisation et restent lisibles.
- Montage partiel : vidéo H.264 centrale copiée, raccords et effets encodés en H.264 CRF 16, audio continu AAC 320 kbit/s, MP4. Montage complet : encodage CPU ou GPU choisi ; sans perte, H.264 CRF 0 / FLAC en MKV. Sans montage : pistes vidéo et audio copiées sans réencodage. Les vidéos terminées apparaissent avant l’analyse.
- Avec IA : résumés par période de cinq minutes (`resume_5min.txt` et `.json`), résumé global, jusqu’à trois propositions de titres validées, texte de miniature et image sélectionnée. `transcription.txt` contient désormais ces notes compactes ; `transcription.json` reste un cache technique local pour éviter de réécouter la vidéo.
- `projet.json` : paramètres, début effectivement retenu, durées réelles, résultats et éventuels avertissements.

Clique sur un titre dans l’interface pour le copier. Ouvre **Modifier la miniature** pour changer l’image ou le texte. Le badge « Épisode » est placé en haut à droite pour laisser la caméra en haut à gauche visible. Les miniatures sont des compositions à partir de vraies images du clip ; l’application ne génère pas de scène fictive.

## Titres, jeu imposé et recherches

Le format est ajouté par l’application, pas par le modèle : **Une accroche précise [DIVE or DIE - Children of Rain #1]**. Le suffixe respecte le jeu saisi et la numérotation choisie. Les noms des fichiers sont adaptés aux caractères autorisés par Windows ; le titre complet est conservé dans `titres.txt`.

Les sources recherchées doivent concerner le jeu saisi. La recherche générale est complétée par une recherche de correspondance exacte sur Steam et les pages officielles indiquées par sa fiche. En cas d’échec réseau, un avertissement apparaît ; l’application ne prétend pas avoir consulté des sources. Le contexte est conservé sept jours pour éviter de refaire les mêmes recherches pour chaque clip. Décoche la recherche pour rester hors ligne.

L’IA propose plusieurs accroches fondées sur les passages du clip, puis un second passage contrôle le jeu, les faits et la précision. Les titres génériques et certaines substitutions fréquentes de jeux sont aussi bloqués par des contrôles déterministes. Un échec de validation conserve les vidéos et indique **À revoir**. La relecture humaine reste utile : un modèle local peut encore mal interpréter une parole.

## Retoucher des clips existants sans tout refaire

Clique sur **Ouvrir un projet existant**, sélectionne `projet.json`, saisis le nom du jeu et clique sur **Refaire les titres et miniatures**. Les vidéos ne sont ni recopiées ni redécoupées. Les anciens titres et miniatures sont sauvegardés dans le dossier `historique` de chaque clip.

Les transcriptions et les huit images sont réutilisées par défaut. Les analyses visuelles sont aussi réutilisées si le clip, ses images et le jeu sont identiques. Décoche **Réutiliser les transcriptions existantes** pour refaire Whisper avec le vocabulaire du jeu lorsqu’une ancienne transcription est trop mauvaise.

Le mode sans montage n’effectue plus la seconde réécriture MP4 « faststart » : aucune qualité vidéo/audio n’est perdue, mais un fichier envoyé tel quel sur un simple serveur web peut nécessiter un téléchargement complet avant lecture. YouTube traite ses propres fichiers après import. Le modèle reste chargé entre les clips pendant 30 minutes. Le rédacteur reçoit désormais des résumés par périodes de cinq minutes préparés localement, avec les actions, enjeux et incertitudes utiles aux titres. Une condensation peut omettre un détail bref : relis les notes affichées pour évaluer les titres. Même modèle Whisper, même effort de décodage, même modèle visuel et mêmes huit images en 1280 × 720.

## Mode IA locale

Le bouton **Préparer l’IA** installe les dépendances Python dans `.venv`, télécharge Whisper base (multilingue) et Ollama portable, puis Gemma 3 4B pour les images et Qwen 3.5 4B pour la rédaction et le contrôle des titres. Prévoir plusieurs Go de téléchargement et environ 12 à 16 Go de disque pour les outils et modèles, en plus des vidéos. L’analyse CPU peut être lente ; Ollama utilise une carte graphique compatible lorsqu’elle est disponible.

En mode local, après la préparation, les paroles et images sont traitées sur le PC. Aucun contenu de VOD n’est envoyé à une API distante. Internet sert à récupérer les logiciels et modèles, et à rechercher le jeu si cette option est cochée. Pas de clé API ni d’abonnement.

**Proposer le début des paroles** examine les 15 premières minutes et propose un point deux secondes avant la première parole reconnue. Tu dois le valider : musique chantée, paroles de jeu ou reconnaissance imparfaite peuvent donner un faux départ. Tu peux toujours saisir le début manuellement.

## Limites utiles

- Sans réencodage, FFmpeg coupe aux images clés. Les durées peuvent varier de quelques secondes, ou davantage si la vidéo contient très peu d’images clés. Le début est avancé à la première image clé disponible pour éviter de conserver l’intro ; cette avance peut retirer un peu du début du contenu.
- Toutes les pistes audio sont conservées (réencodées avec le montage, copiées sans montage) ; la première sert à la transcription et à la détection des pauses. Les sous-titres, pièces jointes et pistes de données ne sont pas exportés.
- Les images sont échantillonnées à huit instants répartis dans chaque clip. L’IA ne regarde pas chaque image de toute la vidéo ; elle peut rater un événement bref. Relis les titres avant publication.
- Sans IA, les titres restent génériques et la miniature utilise un classement simple de luminosité/netteté.
- L’arrêt interrompt FFmpeg rapidement ; une inférence Whisper ou Ollama en cours peut finir avant que l’arrêt soit pris en compte. Les clips terminés sont conservés ; le dernier fichier en cours de découpage peut être incomplet.
- Une erreur d’analyse ne supprime pas les clips. Consulte le journal et les fichiers de transcription conservés.
- Les résultats restent sur le disque après fermeture. Rouvre `projet.json` pour les retrouver dans l’interface.

## Développement et tests

Python 3.12, FFmpeg et FFprobe sont préparés par le dossier `Installation`. Aucun composant de Codex n’est requis sur un autre PC. Pour développer, utilise `.venv`; `build_desktop.py` recrée l’EXE Windows avec PyInstaller. Le binaire est un lanceur du programme et de ses dépendances dans ce dossier, pas un fichier autonome à déplacer seul.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe desktop.py
.\.venv\Scripts\python.exe build_desktop.py
```

Les tests génèrent une vidéo synthétique, vérifient les durées, le retrait de l’intro, le regroupement du dernier segment court et comparent les empreintes SHA-256 des paquets vidéo pour prouver la copie sans perte ni duplication.

Sources techniques : [FFmpeg segment muxer](https://ffmpeg.org/ffmpeg-formats.html#segment), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Gemma 3 4B dans Ollama](https://ollama.com/library/gemma3:4b), [API locale Ollama](https://docs.ollama.com/api/chat).


## Mode OpenAI avec une clé API

Dans **Quelle IA utiliser ?**, choisis **OpenAI · avec ma clé API**. Le modèle OpenAI choisi analyse les huit images, rédige les titres et contrôle leur fidélité au jeu et aux faits. La recherche du jeu conserve son périmètre strict. Whisper et Qwen restent locaux : seuls les résumés de cinq minutes, les images et le contexte du jeu partent vers OpenAI, pas la transcription détaillée, le fichier vidéo ni l’audio. Le découpage sans montage reste sans réencodage ; le montage nécessite un rendu vidéo local. Les miniatures restent des compositions locales à partir des images du clip.

1. Ouvre [API keys](https://platform.openai.com/api-keys), connecte-toi et sélectionne ton projet.
2. Clique sur **Create new secret key**, nomme la clé **VOD Atelier**, puis copie la clé secrète complète dans l’application. Ce n’est ni ton mot de passe ChatGPT, ni une clé administrateur. Si tu limites ses permissions, autorise Responses en écriture et Models en lecture.
3. Configure la [facturation API](https://platform.openai.com/settings/organization/billing/overview) et les crédits. L’API est facturée séparément de l’abonnement ChatGPT, selon l’usage. Consulte les [tarifs](https://developers.openai.com/api/docs/pricing).
4. Clique sur **Vérifier la clé** : seul l’accès au modèle est testé, sans génération ni contenu du clip. Cela ne confirme pas le solde disponible ni les permissions de génération.
5. Lance les épisodes ou rouvre un projet pour refaire les titres sans redécouper.

La clé n’est stockée ni dans les fichiers projet, ni dans le navigateur, ni dans les journaux. Elle reste en mémoire dans la page et pendant le traitement. Il faut la recoller après actualisation/fermeture de la page. Ne l’envoie pas dans le chat. Les requêtes Responses utilisent `store: false` ; cela ne remplace pas les [règles de conservation des données API](https://developers.openai.com/api/docs/guides/your-data).

Les erreurs de clé, accès, connexion ou quota sont affichées sans divulguer le secret. Aucun basculement automatique vers un autre fournisseur. Les analyses visuelles en cache distinguent le fournisseur et le modèle ; les transcriptions restent réutilisables dans les deux modes.

Documentation : [premiers pas API](https://developers.openai.com/api/docs/quickstart), [modèle GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1).


## Choisir le modèle OpenAI et comparer les coûts

Le champ **Modèle OpenAI** apparaît quand tu choisis OpenAI. Sept modèles sont proposés avec leurs prix indicatifs ; **Autre modèle** permet de saisir un identifiant exact, y compris une version datée. Le choix est mémorisé sur ce navigateur et enregistré dans les résultats du projet. La clé API reste uniquement en mémoire.

Tarifs standard en dollars par million de tokens, vérifiés le 30 septembre 2026, hors réduction du cache :

| Modèle | Entrée | Sortie |
| --- | ---: | ---: |
| [gpt-6-luna](https://developers.openai.com/api/docs/models/gpt-6-luna) | 0,10 $ | 0,50 $ |
| [gpt-4.1-nano](https://developers.openai.com/api/docs/models/gpt-4.1-nano) | 0,10 $ | 0,40 $ |
| [gpt-4.1-mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini) | 0,40 $ | 1,60 $ |
| [gpt-4.1](https://developers.openai.com/api/docs/models/gpt-4.1) | 2,00 $ | 8,00 $ |
| [gpt-5.4-nano](https://developers.openai.com/api/docs/models/gpt-5.4-nano) | 0,20 $ | 1,25 $ |
| [gpt-5.4-mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) | 0,75 $ | 4,50 $ |
| [gpt-5.4](https://developers.openai.com/api/docs/models/gpt-5.4) | 2,50 $ | 15,00 $ |

Ce ne sont pas des prix par clip : les huit images, la longueur des résumés et les différents passages de rédaction et de contrôle contribuent au coût. Le catalogue est indicatif ; consulte les liens officiels pour les tarifs à jour. Les modèles plus petits peuvent donner des titres moins pertinents : compare les résultats sur un clip.

Le modèle s’applique à toutes les étapes OpenAI du prochain traitement, y compris la préparation du contexte du jeu si elle n’est pas déjà en cache. **Vérifier la clé** vérifie l’accès à ce modèle précis sans génération. Un modèle personnalisé doit accepter Responses, les images et les sorties JSON structurées ; une erreur sera affichée si ce n’est pas le cas. Il n’y a pas de remplacement automatique par un autre modèle. Les modèles GPT-5.4 proposés utilisent l’effort de raisonnement `none` pour éviter les tokens supplémentaires de raisonnement.

Changer de modèle OpenAI distingue les caches d’analyse des images. Les résumés locaux restent réutilisables. Le texte de Whisper et les images extraites restent réutilisables sans perte. Le contexte factuel du jeu déjà en cache peut être réutilisé.


## Réponses incomplètes et GPT-6 Luna

GPT-6 Luna est maintenant proposé directement dans la liste. L’application conserve son effort de raisonnement `medium`. La limite de sortie comprend aussi les tokens de raisonnement : Luna dispose de 16 384 tokens au lieu d’hériter de la limite locale de 500 tokens pour les images. Cette limite est un plafond, pas un coût fixe par appel.

Si l’API signale précisément `max_output_tokens`, un seul nouvel essai est fait, avec une limite doublée et plafonnée à 32 768 tokens. Les deux appels peuvent être facturés ; leurs consommations sont additionnées dans les informations d’analyse. Une réponse tronquée n’est jamais publiée. Pour un filtrage du contenu ou une cause non précisée, il n’y a pas de relance automatique. Le journal indique l’étape, le modèle et la limite atteinte pour permettre un diagnostic précis. Les transcriptions et les étapes déjà terminées restent réutilisables.

Sources : [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna), [raisonnement et limites de sortie](https://developers.openai.com/api/docs/guides/reasoning).


Pour installer les dépendances de développement dans un environnement Python 3.12 :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

Les tests automatiques ne font pas d’appels API payants. Le test manuel des titres locaux s’utilise avec un projet existant et un jeu explicite :

```powershell
.\.venv\Scripts\python.exe tests/try_editorial.py "chemin/vers/projet.json" --game "Nom exact du jeu" --clip 1
```

Ce test crée ses résultats séparément sous `tests/output`. Les VOD, clips, modèles, dépendances téléchargées, fichiers de session, clés et caches sont exclus de Git.


## Tags YouTube communs au jeu

Un seul fichier **tags.txt** est créé à la racine du dossier du projet, à côté de **projet.json**. Sa liste est commune à tous les épisodes : nom du jeu, variantes avec gameplay/français et contenu gaming francophone. Elle ne dépend pas des paroles ni des événements d’un clip. Les genres ne sont ajoutés que lorsqu’ils figurent dans le contexte du jeu recherché. Sans nom de jeu, seuls les tags généraux de contenu francophone sont utilisés.

Le fichier contient uniquement les tags séparés par des virgules, prêts à copier dans YouTube Studio. Le comptage reste à **500 caractères maximum**, séparateurs inclus, et inclut les deux guillemets implicitement comptés par YouTube pour chaque tag contenant un espace. Les doublons sont retirés et les tags sont conservés entiers. Le fichier est recréé si tu refais la publication avec un autre jeu.

Règle officielle : [YouTube — snippet.tags](https://developers.google.com/youtube/v3/docs/videos#snippet.tags).


## Résumés de cinq minutes

Whisper conserve la même reconnaissance de tout le clip sur le PC. Qwen prépare ensuite un résumé de 1 à 2 phrases par période de cinq minutes, avec au maximum deux actions, enjeux ou difficultés précis. Un clip de 20 minutes fournit quatre périodes ; le dernier intervalle est plus court si nécessaire. Les hypothèses et les passages incertains ne doivent pas devenir des faits accomplis.

Les résumés sont **toujours locaux**, y compris en mode OpenAI : pas de nouvel appel API payant pour les produire. Whisper et Qwen doivent donc être préparés dans les deux modes. Le modèle OpenAI choisi conserve la rédaction, le contrôle des titres et l’analyse des huit images. Aucun basculement payant vers une transcription complète en cas d’échec du résumé ; le clip est indiqué « À revoir » et les caches sont conservés.

Les notes sont affichées sous **Résumés par période de 5 minutes** pour chaque épisode et enregistrées dans `resume_5min.txt` / `resume_5min.json`. La taille du texte détaillé et celle des notes sont indiquées. Les résumés sont réutilisés lorsque la transcription, le jeu et le modèle local restent identiques, même si tu changes le modèle OpenAI. Rouvre un projet puis clique sur **Refaire les titres et miniatures**, en gardant la réutilisation des transcriptions, pour appliquer cette méthode sans découper ni écouter à nouveau les clips.

Cette méthode réduit le volume de texte envoyé pour les titres, donc la part de coût liée aux tokens d’entrée. Le coût des images, sorties et éventuels réessais reste présent. Elle n’accélère pas directement Whisper et ajoute une étape de résumé local ; le temps total dépend du PC et du modèle choisi. Un résumé peut perdre des détails : il s’agit de l’essai à cinq minutes demandé, pas d’une promesse de qualité identique au texte intégral.


## Dernier morceau court regroupé

Si le dernier morceau fait moins que la durée choisie (20 minutes par défaut), il est automatiquement intégré à l’avant-dernier épisode. Exemple : sept clips de 20 minutes, puis 20 + 10 minutes, deviennent sept clips de 20 minutes et un dernier de 30 minutes. Une VOD plus courte qu’un épisode reste un seul clip.

Le regroupement est prévu avant le découpage : l’application omet la dernière coupe. Sans montage, FFmpeg copie les pistes en une passe ; avec montage, le dernier épisode plus long est rendu directement, sans créer deux vidéos intermédiaires à recoller. Les très petits écarts de durée dus aux horodatages et aux images clés n’affectent pas la logique des périodes prévues. L’estimation affichée tient compte de cette règle.

L’analyse porte ensuite sur le clip entier obtenu. Un dernier épisode de 30 minutes reçoit six résumés de cinq minutes, un titre et une miniature pour l’ensemble. La règle s’applique aux nouvelles créations ; rouvrir un ancien projet pour refaire ses titres ne modifie pas ses fichiers vidéo.

## Titres courts et intrigants

L’IA propose trois titres aux angles différents : association étrange ou contradiction, réaction forte ou absurde, question ou mystère. Un titre n’est pas un résumé : il peut omettre du contexte, être une liste de mots et accentuer quelques mots en majuscules. La cible est de 3 à 7 mots, exceptionnellement jusqu’à 10, avant le suffixe `[Nom du jeu #n]` ajouté par l’application.

Le contrôle indépendant accepte ces formes courtes et vérifie toujours leur sous-entendu contre les résumés du clip. Il écarte les inventions, les références à d’autres jeux, les rubriques descriptives et les reformulations trop proches. Ces consignes sont communes à l’IA locale et à OpenAI. Pour appliquer le style à un projet existant, utilise **Refaire les titres et miniatures** avec la réutilisation des transcriptions.

Pour le mode navigateur de développement uniquement, lance `app.py` ou `launch.py --browser`. Le démarrage habituel utilise la fenêtre bureau.


## Montage et coupes pendant les pauses de voix

Place **Starting Screen.mp4** et **Stinger.webm** dans le dossier `Montage` ([instructions](Montage/Lisez-moi.md)). Le starting screen est joué pendant deux secondes avant le stinger. La transparence WebM VP9 est décodée avec libvpx ; le changement de fond se fait au milieu d’un passage opaque quand le fichier en possède un. L’écran de jeu reste figé pendant la révélation, puis le contenu et ses paroles commencent en entier. L’intro ajoute environ cinq secondes avec le stinger actuel. Elle est exclue des images candidates et des résumés de cinq minutes. Le fondu au noir affecte les deux dernières secondes de l’image ; les paroles restent audibles.

Le **montage partiel** évite de réencoder la vidéo centrale sur les sources compatibles. Le **montage complet** réencode toutes les images et reste disponible dans « Méthode de montage ». Le rendu **sans perte de compression** est une option pour ne pas ajouter de perte par compression : H.264 CRF 0 / FLAC, MKV. Le rendu **haute qualité**, sélectionné par défaut, utilise H.264 CRF 16 / AAC 320 kbit/s, MP4 : une compression avec perte légère, qui donne des fichiers plus petits. Les compositions et conversions de l’intro restent des traitements d’image ; « sans perte de compression » ne signifie pas que chaque pixel modifié par le montage reste identique. Le test vérifie qu’une image de jeu sans effet est identique au décodage de la source SDR utilisée. Le montage HDR n’est pas pris en charge ; conserve le mode copie pour une source HDR.

**Couper pendant une pause de voix** analyse localement de petites fenêtres autour des limites prévues avec Silero VAD, fourni par faster-whisper. La musique ne constitue pas à elle seule une voix. L’application cherche une pause d’au moins 500 ms, avec une marge autour des paroles détectées, à ±30 secondes. Elle conserve la continuité des segments et n’efface aucun intervalle. Chaque épisode ordinaire reste dans cette tolérance ; le dernier regroupé peut être plus long. La détection peut confondre des voix de jeu ou manquer une voix faible : si aucun point utilisable n’est trouvé, la limite prévue est conservée et le journal l’indique. En mode copie, une pause doit aussi contenir une image clé ; les limites réelles restent soumises aux images clés de la source.

La règle du dernier morceau court reste fondée sur les périodes prévues, avant les légers ajustements de silence. Une petite réduction du dernier épisode à cause d’une coupe décalée n’ajoute pas un nouveau regroupement. Rouvrir un projet pour refaire ses titres ne remonte pas les vidéos existantes. Les tags communs restent dans le `tags.txt` du projet.


## Montage partiel : copie de la vidéo centrale

Ce mode est sélectionné par défaut pour les nouveaux montages. L’intro et le début jusqu’à la prochaine image IDR sont encodés, le centre est copié, puis le dernier GOP et le fondu sont encodés. Le CPU encode ces courts raccords en H.264 CRF 16 au profil de la source. Il reste parfois quelques secondes à encoder en plus des effets, selon l’espacement des images clés. La partie copiée conserve ses images et ses horodatages, y compris les variations de cadence existantes. La résolution est celle des images réelles de ce clip ; une VOD dont l’en-tête annonce 1080p mais dont le jeu est en 720p ne voit plus son centre agrandi artificiellement.

La première version prend en charge le H.264 SDR 8 bits, progressif, à résolution constante dans le clip, avec des images IDR indépendantes. Une source AV1 ou HEVC, un changement de résolution, un GOP ouvert, une origine temporelle décalée, un clip trop court ou un échec de validation entraîne un montage complet pour ce clip. Le rendu sans perte utilise également le montage complet. La raison du repli est affichée ; le choix CPU/GPU reste celui du montage complet ou de secours. Rouvrir un ancien projet ne remonte pas ses vidéos.

Le codec du centre doit être conservé : une VOD H.264 produit donc un MP4 H.264 en mode partiel, même si AV1 est choisi pour le montage complet. L’audio reste traité une seule fois en AAC 320 kbit/s pour assembler l’intro et les paroles sans multiplier les raccords AAC et leur délai de priming. **Seules les images centrales sont copiées sans réencodage ; l’audio reste réencodé sur toute la durée.** Toutes les pistes sont conservées. Les résumés de cinq minutes, les titres et les miniatures gardent leur fonctionnement.

Les contrôles comparent les PTS et DTS de chaque paquet central avant et après l’assemblage, vérifient la durée et les pistes, puis décodent les deux raccords. Les erreurs et annulations suppriment le fichier incomplet et les fichiers temporaires. Des tests vérifient les images centrales bit à bit après décodage, l’absence de doublon ou de trou aux raccords, le fondu et les deux pistes audio.

Mesure du 3 octobre 2026 sur un **vrai clip de 20 minutes**, avec les mêmes assets, en H.264 1280 × 720, sur le PC équipé de la RX 9070 XT. Le montage complet utilise AMF CQP 20 avec décodage D3D11VA ; le montage partiel encode ses raccords sur le CPU. La mesure partielle inclut l’inspection des images clés, les copies, le traitement audio et les validations.

| Méthode | Temps de montage | Taille du fichier |
| --- | ---: | ---: |
| Montage complet · GPU AMD H.264 | 226,73 s (3 min 47 s) | 2 681,18 Mo |
| Montage partiel · H.264 copié au centre | 78,60 s (1 min 19 s) | 597,56 Mo |

Le centre copié dure **1 196 secondes**, et les images encodées environ **9,07 secondes**, intro comprise. Le gain mesuré est d’environ **65 %**, soit un montage **2,9 fois plus rapide**. L’audio représente désormais la majeure partie du temps (environ 70 secondes sur cet extrait) ; l’encodage de l’image n’est plus le principal coût. Pour neuf clips de vingt minutes, cette mesure donne une estimation de **34 minutes contre 12 minutes**, hors recherche des pauses, transcription et analyse IA. Cette extrapolation dépend de la source, de la charge du PC et du disque.

Sur le clip de vingt minutes, les **70 317 paquets vidéo centraux hors images clés** sont identiques au fichier source, et les **70 915 images centrales** gardent leurs horodatages sans variation supplémentaire ni DTS non monotone. Les images clés peuvent recevoir les paramètres H.264 nécessaires au raccord. Un autre contrôle sur soixante secondes compare les **3 360 images centrales après décodage**, toutes identiques à la source.

Référence technique : [FFmpeg — concat demuxer](https://ffmpeg.org/ffmpeg-formats.html#concat), notamment la compatibilité des streams et la conversion H.264 en Annex B pour les paramètres de décodage aux raccords.

## Montage avec un GPU

Dans **Encodeur du montage complet ou de secours**, choisis **GPU AMD · H.264 haute qualité** ou **GPU · AV1 haute qualité (automatique)**. Ce choix est mémorisé localement ; un ancien choix « AMD AV1 » est migré vers la détection automatique. Pour AV1, l’application essaie les moteurs AMD AMF, NVIDIA NVENC et Intel Quick Sync dans cet ordre et garde le premier capable d’encoder un petit MP4 à la résolution et à la cadence de la source. Il faut un GPU capable d’**encoder** en AV1, son pilote et un FFmpeg comprenant l’encodeur correspondant ; la seule lecture AV1 ne suffit pas. La marque réellement utilisée est affichée sur les clips.

H.264 utilise AMD AMF avec l’usage `high_quality`, le préréglage `quality` et CQP 20. AV1 AMD conserve `av1_amf`, l’usage `transcoding`, le préréglage `quality`, CQP 40 et NV12 ; préanalyse et préencodage sont désactivés. NVIDIA utilise `av1_nvenc`, P6/HQ et VBR à qualité constante CQ 16 sans débit cible imposé. Intel utilise `av1_qsv`, le préréglage `slow` et ICQ 16 sans débit cible imposé. Les échelles de qualité diffèrent entre les moteurs. Les profils AMD ont été comparés au rendu CPU H.264 CRF 16 sur le PC de développement ; les chemins NVIDIA et Intel et leur repli CPU sont testés avec des pilotes simulés, sans mesure matérielle de qualité sur ces marques. Le décodage H.264 par D3D11VA reste activé pour le moteur AMD testé. Les effets, la transparence du stinger et le fondu restent calculés sur le CPU. Les résumés, les titres et la détection des pauses restent identiques.

FFmpeg vérifie réellement l’initialisation du moteur GPU à la résolution et à la cadence du fichier avant le montage. Pour AV1, un petit MP4 est aussi contrôlé afin de vérifier que le pilote conserve les dimensions demandées. En mode AV1 automatique, un moteur indisponible ou incompatible laisse place au suivant. Si aucun ne fonctionne, le CPU prend le relais. Si le rendu GPU échoue, le fichier incomplet est supprimé et ce clip est recommencé une fois en H.264 sur le CPU ; les suivants restent sur le CPU. Le moteur et le codec effectivement utilisés sont enregistrés pour chaque clip et affichés dans l’interface. Le rendu sans perte et les sources dont le format de couleur n’est pas YUV 4:2:0 8 bits utilisent le CPU pour préserver ce choix de qualité. Le montage HDR reste indisponible.

La RX 9070 XT a été détectée et testée le 2 octobre 2026 avec le FFmpeg et le pilote AMD déjà présents sur le PC. Sur un extrait réel de 20 secondes, avec l’intro, le stinger, le fondu et l’audio, le rendu donne :

| Rendu | Temps du montage | Taille | VMAF moyen du contenu sans effets |
| --- | ---: | ---: | ---: |
| CPU · H.264 CRF 16 | 11,21 s | 38,23 Mo | 97,82 |
| AMD · H.264 CQP 20 + décodage D3D11VA | 28,67 s | 60,59 Mo | 98,09 |
| AMD · AV1 CQP 40 + décodage D3D11VA | 11,84 s | 41,63 Mo | 97,86 |

Le contrôle compare les images alignées à un rendu sans perte du même montage, sans l’intro ni la fin fondue. Le test H.264 GPU avec décodage CPU et celui avec décodage D3D11VA ont produit des fichiers identiques (SHA-256). AV1 donne ici un fichier environ 31 % plus petit que H.264 GPU, à une qualité mesurée comparable au CPU, mais environ 9 % plus gros que le CPU. La vitesse varie fortement entre les essais ; AV1 n’assure pas un gain de temps. Ce sont des mesures sur un extrait, pas une promesse pour toutes les VOD ni une garantie de qualité identique pour tous les détails. Les images complexes, la résolution, la cadence et la charge du PC peuvent modifier le résultat. Les fichiers AV1 restent des MP4, mais le lecteur utilisé doit prendre en charge le codec AV1. L’extraction des huit images destinées aux miniatures a aussi été vérifiée sur un montage AV1. Le CPU reste le choix initial ; le GPU est une option explicite.

Sources techniques : [fiche AMD RX 9070 XT](https://www.amd.com/en/products/graphics/desktops/radeon/9000-series/amd-radeon-rx-9070xt.html), [réglages AMF dans FFmpeg — AMD GPUOpen](https://github.com/GPUOpen-LibrariesAndSDKs/AMF/wiki/AMF%20Encoder%20Settings%20and%20Tuning%20in%20FFmpeg).

Sources pour les nouveaux moteurs : [NVIDIA NVENC dans FFmpeg](https://docs.nvidia.com/video-technologies/video-codec-sdk/13.1/ffmpeg-with-nvidia-gpu/index.html), [encodeurs Intel QSV — FFmpeg](https://ffmpeg.org/ffmpeg-codecs.html#QSV-Encoders).
