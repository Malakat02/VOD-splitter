"""Per-job provider selection. API secrets live only in memory."""
from contextvars import ContextVar
import json
import re
import time
import urllib.request
import urllib.error

SETTINGS = ContextVar('ai_settings', default={})
OPENAI_MODEL = 'gpt-4.1'
MODEL_CATALOG = [
    {'id': 'gpt-6-luna', 'input': .10, 'output': .50, 'hint': 'Modèle économique avec raisonnement. Budget de réponse adapté à Luna ; les tokens de raisonnement sont facturés en sortie.'},
    {'id': 'gpt-4.1-nano', 'input': .10, 'output': .40, 'hint': 'Le moins cher de cette sélection. À essayer sur un clip avant de traiter toute la VOD.'},
    {'id': 'gpt-4.1-mini', 'input': .40, 'output': 1.60, 'hint': 'Une option économique pour commencer à comparer les titres.'},
    {'id': 'gpt-4.1', 'input': 2., 'output': 8., 'hint': 'Le modèle utilisé jusque-là dans l’application.'},
    {'id': 'gpt-5.4-nano', 'input': .20, 'output': 1.25, 'hint': 'Une autre option nano à faible coût. Compare la pertinence des titres sur le même clip.'},
    {'id': 'gpt-5.4-mini', 'input': .75, 'output': 4.50, 'hint': 'Une autre option mini à comparer selon tes résultats.'},
    {'id': 'gpt-5.4', 'input': 2.50, 'output': 15., 'hint': 'Plus coûteux. À tester si les modèles plus petits ne te satisfont pas.'},
]


def selected_model():
    return SETTINGS.get().get('model', OPENAI_MODEL)


def configure(config):
    provider = config.get('provider', 'local')
    if provider not in ('local', 'openai'):
        raise ValueError('Choisis IA locale ou OpenAI.')
    key = str(config.pop('api_key', '')).strip()
    model = str(config.get('openai_model', OPENAI_MODEL)).strip()
    if provider == 'openai' and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', model):
        raise ValueError('Indique un identifiant de modèle OpenAI valide, par exemple gpt-4.1-mini.')
    if provider == 'openai' and config.get('ai') and (not key or any(c.isspace() for c in key)):
        raise ValueError('Colle ta clé API OpenAI dans le champ prévu.')
    return SETTINGS.set({'provider': provider, 'key': key, 'model': model})


def remote():
    return SETTINGS.get().get('provider') == 'openai'


def model_id(local_model):
    return 'openai/' + selected_model() if remote() else local_model


def ready(status):
    return status['speech'] and status.get('editor', False) if remote() else status['ready']


def request(path, payload=None):
    key = SETTINGS.get().get('key', '')
    if not key:
        raise ValueError('Clé API OpenAI manquante.')
    req = urllib.request.Request('https://api.openai.com/v1/' + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    # Never forward a credential to a redirect target, or log remote error bodies.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=180) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        explanations = {401: 'Clé API incorrecte ou révoquée.', 403: 'Cette clé ne dispose pas des autorisations nécessaires.',
            404: f'Le modèle {selected_model()} est introuvable ou indisponible pour ce projet.',
            429: 'Quota ou limite atteint : vérifie les crédits et limites du projet OpenAI.',
            400: 'OpenAI a refusé la requête. Vérifie que le modèle choisi accepte Responses, les images et les sorties JSON structurées.'}
        raise RuntimeError(f'OpenAI HTTP {exc.code} : ' + explanations.get(exc.code, 'Service indisponible, réessaie plus tard.')) from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('Connexion à OpenAI impossible ou délai dépassé. Vérifie Internet puis réessaie.') from None


def chat(messages, runner, timings, stage, *, images=None, json_output=True, tokens=1800, schema=None):
    runner.check()
    inputs = [{'role': m['role'], 'content': [{'type': 'input_text', 'text': m['content']}]} for m in messages]
    if images:
        inputs[-1]['content'].extend({'type': 'input_image', 'image_url': 'data:image/jpeg;base64,' + im, 'detail': 'high'} for im in images)
    model = selected_model()
    luna = bool(re.fullmatch(r'gpt-6-luna(?:-\d{4}-\d{2}-\d{2})?', model))
    # Preserve Luna's default reasoning quality. Its budget must include hidden reasoning
    # as well as the visible JSON; the local model's 500-token vision budget is insufficient.
    budget = max(16384, tokens) if luna else max(2048, tokens)
    payload = {'model': model, 'input': inputs, 'store': False, 'max_output_tokens': budget}
    if luna:
        payload['reasoning'] = {'effort': 'medium'}
    if model in {'gpt-5.4', 'gpt-5.4-mini', 'gpt-5.4-nano'} or re.fullmatch(r'gpt-5\.4(?:-mini|-nano)?-\d{4}-\d{2}-\d{2}', model):
        payload['reasoning'] = {'effort': 'none'}
    if json_output:
        payload['text'] = {'format': {'type': 'json_schema', 'name': 'vod_analysis', 'strict': True, 'schema': schema} if schema else {'type': 'json_object'}}
    started = time.perf_counter()
    for attempt in range(2):
        runner.check()
        result = request('responses', payload)
        runner.check()
        reason = (result.get('incomplete_details') or {}).get('reason')
        usage = result.get('usage') or {}
        for name in ('input_tokens', 'output_tokens'):
            count = usage.get(name)
            if isinstance(count, int):
                timings[stage + '_' + name] = timings.get(stage + '_' + name, 0) + count
        reasoning_tokens = (usage.get('output_tokens_details') or {}).get('reasoning_tokens')
        if isinstance(reasoning_tokens, int):
            timings[stage + '_reasoning_tokens'] = timings.get(stage + '_reasoning_tokens', 0) + reasoning_tokens
        if result.get('status') == 'completed':
            break
        if result.get('status') == 'incomplete' and reason == 'max_output_tokens':
            runner.log(f'{model} · {stage} : limite de {payload["max_output_tokens"]} tokens atteinte (raisonnement inclus).')
            if attempt == 0 and payload['max_output_tokens'] < 32768:
                payload['max_output_tokens'] = min(32768, payload['max_output_tokens'] * 2)
                runner.log(f'Un seul nouvel essai avec une limite de {payload["max_output_tokens"]} tokens. Cet essai peut ajouter un coût API.')
                continue
            raise ValueError(f'{model} : réponse tronquée après {payload["max_output_tokens"]} tokens à l’étape {stage}, raisonnement compris. Aucun résultat partiel publié. Essaie un autre modèle ; les étapes terminées sont conservées.')
        if result.get('status') == 'incomplete' and reason == 'content_filter':
            raise ValueError(f'OpenAI a interrompu l’analyse à l’étape {stage} pour filtrage du contenu. Un nouvel essai automatique ne résoudrait pas ce refus.')
        raise ValueError(f'Réponse OpenAI incomplète à l’étape {stage} (cause non précisée par l’API). Les étapes terminées sont conservées.')
    timings[stage] = round(time.perf_counter() - started, 2)
    parts = [c for item in result.get('output', []) for c in item.get('content', [])]
    if any(c.get('type') == 'refusal' for c in parts):
        raise ValueError('OpenAI a refusé cette analyse. Aucun titre non validé ne sera publié.')
    answer = ''.join(c.get('text', '') for c in parts if c.get('type') == 'output_text')
    try:
        return json.loads(answer) if json_output else answer
    except ValueError:
        raise ValueError('Réponse OpenAI illisible. Réessaie l’analyse.') from None
