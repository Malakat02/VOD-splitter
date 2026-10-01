# VOD-splitter · VOD Atelier

Application Windows locale pour transformer une longue VOD en épisodes.

## Installer depuis GitHub

Télécharge le dépôt avec **Code → Download ZIP**, puis extrais le ZIP, ou clone-le avec Git. Installe Python 3.12 et FFmpeg (avec FFprobe) et rends leurs commandes accessibles dans le PATH Windows. Le dépôt contient le programme, pas les modèles IA ni les vidéos.

Double-clique sur **Lancer VOD Atelier.cmd**. Le lanceur crée le dossier `.venv` et installe Pillow si nécessaire. Dans l’interface, **Préparer l’IA** installe les dépendances restantes et les modèles. Le mode OpenAI utilise ta propre clé API et garde Whisper sur le PC.

## Ouvrir l’application

Double-clique sur **Lancer VOD Atelier.cmd**. L’interface s’ouvre dans le navigateur. Le serveur écoute uniquement sur ton ordinateur, à une adresse `127.0.0.1`.

1. Choisis ta vidéo avec **Parcourir**, ou colle son chemin. Le sélecteur s’ouvre dans la page : un clic ouvre un dossier, puis sélectionne le fichier et clique sur **Choisir**. Les boutons de disques permettent de passer de C: à D: ou E:, et le champ de chemin permet d’ouvrir directement un dossier.
2. Indique le début du contenu : `05:00` retire cinq minutes. La durée des épisodes commence après cette intro.
3. Garde **20 minutes**, ou choisis une autre durée.
4. Saisis le **nom exact du jeu** et le **numéro du premier clip**. Le jeu saisi fixe le périmètre de recherche et d’analyse : il ne doit pas être remplacé par un jeu supposé à partir de Whisper.
5. Garde **Rechercher le contexte du jeu sur Internet** pour utiliser des sources sur le jeu. Les liens consultés sont affichés. Seul le nom du jeu sert à la recherche ; aucune vidéo, image ou transcription n’est envoyée au moteur de recherche. En mode OpenAI, les résumés de cinq minutes et les huit images sont envoyés à OpenAI pour l’analyse ; la transcription détaillée reste locale.
6. Choisis **IA locale** ou **OpenAI**, puis coche **Analyser avec l’IA** pour obtenir les titres et la miniature choisie par le modèle.
7. Clique sur **Créer mes épisodes**.

Les résultats sont dans un nouveau sous-dossier de **Clips VOD**, à côté de la vidéo, sauf si tu choisis une autre destination. Le bouton **Choisir** utilise le même sélecteur intégré : ouvre le dossier voulu et confirme avec **Choisir**. Les fichiers existants ne sont pas écrasés. Une heure de contenu utile donne environ trois épisodes de 20 minutes. Une VOD d’une heure dont on retire cinq minutes donne environ 20 + 35 minutes : le dernier morceau court est intégré au précédent.

## Contenu des résultats

- `clip_001.mp4`, etc. : pistes vidéo et audio copiées sans réencodage. Les vidéos apparaissent dès la fin du découpage, avant l’analyse. Avec un nom de jeu, elles sont ensuite renommées d’après le premier titre validé. Certains codecs utilisent MKV pour conserver leur format.
- Dossier `clip_001` : miniature JPEG 1280 × 720, huit images candidates et planche de contact.
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

Le découpage n’effectue plus la seconde réécriture MP4 « faststart » : aucune qualité vidéo/audio n’est perdue, mais un fichier envoyé tel quel sur un simple serveur web peut nécessiter un téléchargement complet avant lecture. YouTube traite ses propres fichiers après import. Le modèle reste chargé entre les clips pendant 30 minutes. Le rédacteur reçoit désormais des résumés par périodes de cinq minutes préparés localement, avec les actions, enjeux et incertitudes utiles aux titres. Une condensation peut omettre un détail bref : relis les notes affichées pour évaluer les titres. Même modèle Whisper, même effort de décodage, même modèle visuel et mêmes huit images en 1280 × 720.

## Mode IA locale

Le bouton **Préparer l’IA** installe les dépendances Python dans `.venv`, télécharge Whisper base (multilingue) et Ollama portable, puis Gemma 3 4B pour les images et Qwen 3.5 4B pour la rédaction et le contrôle des titres. Prévoir plusieurs Go de téléchargement et environ 12 à 16 Go de disque pour les outils et modèles, en plus des vidéos. L’analyse CPU peut être lente ; Ollama utilise une carte graphique compatible lorsqu’elle est disponible.

En mode local, après la préparation, les paroles et images sont traitées sur le PC. Aucun contenu de VOD n’est envoyé à une API distante. Internet sert à récupérer les logiciels et modèles, et à rechercher le jeu si cette option est cochée. Pas de clé API ni d’abonnement.

**Proposer le début des paroles** examine les 15 premières minutes et propose un point deux secondes avant la première parole reconnue. Tu dois le valider : musique chantée, paroles de jeu ou reconnaissance imparfaite peuvent donner un faux départ. Tu peux toujours saisir le début manuellement.

## Limites utiles

- Sans réencodage, FFmpeg coupe aux images clés. Les durées peuvent varier de quelques secondes, ou davantage si la vidéo contient très peu d’images clés. Le début est avancé à la première image clé disponible pour éviter de conserver l’intro ; cette avance peut retirer un peu du début du contenu.
- Toutes les pistes audio sont copiées ; la première sert à la transcription. Les sous-titres, pièces jointes et pistes de données ne sont pas exportés.
- Les images sont échantillonnées à huit instants répartis dans chaque clip. L’IA ne regarde pas chaque image de toute la vidéo ; elle peut rater un événement bref. Relis les titres avant publication.
- Sans IA, les titres restent génériques et la miniature utilise un classement simple de luminosité/netteté.
- L’arrêt interrompt FFmpeg rapidement ; une inférence Whisper ou Ollama en cours peut finir avant que l’arrêt soit pris en compte. Les clips terminés sont conservés ; le dernier fichier en cours de découpage peut être incomplet.
- Une erreur d’analyse ne supprime pas les clips. Consulte le journal et les fichiers de transcription conservés.
- Les résultats restent sur le disque après fermeture. Rouvre `projet.json` pour les retrouver dans l’interface.

## Développement et tests

Python 3.12, FFmpeg et FFprobe sont nécessaires. Sur ce PC, le lanceur réutilise le Python fourni avec Codex pour son environnement virtuel. Pour un autre PC, installer Python et FFmpeg, puis lancer le même fichier CMD.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe app.py
```

Les tests génèrent une vidéo synthétique, vérifient les durées, le retrait de l’intro, le regroupement du dernier segment court et comparent les empreintes SHA-256 des paquets vidéo pour prouver la copie sans perte ni duplication.

Sources techniques : [FFmpeg segment muxer](https://ffmpeg.org/ffmpeg-formats.html#segment), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Gemma 3 4B dans Ollama](https://ollama.com/library/gemma3:4b), [API locale Ollama](https://docs.ollama.com/api/chat).


## Mode OpenAI avec une clé API

Dans **Quelle IA utiliser ?**, choisis **OpenAI · avec ma clé API**. Le modèle OpenAI choisi analyse les huit images, rédige les titres et contrôle leur fidélité au jeu et aux faits. La recherche du jeu conserve son périmètre strict. Whisper et Qwen restent locaux : seuls les résumés de cinq minutes, les images et le contexte du jeu partent vers OpenAI, pas la transcription détaillée, le fichier vidéo ni l’audio. Le découpage reste sans réencodage. Les miniatures restent des compositions locales à partir des images du clip.

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

Le regroupement est prévu avant le découpage : FFmpeg omet la dernière coupe et copie les pistes vidéo/audio en une seule passe, sans réencodage ni recopie des deux derniers fichiers. Les très petits écarts de durée dus aux horodatages et aux images clés n’affectent pas la logique des périodes prévues. L’estimation affichée tient compte de cette règle.

L’analyse porte ensuite sur le clip entier obtenu. Un dernier épisode de 30 minutes reçoit six résumés de cinq minutes, un titre et une miniature pour l’ensemble. La règle s’applique aux nouvelles créations ; rouvrir un ancien projet pour refaire ses titres ne modifie pas ses fichiers vidéo.
