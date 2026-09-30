import json
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ai_provider as provider
from core import Runner
import analysis_local


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.config = {'provider': 'openai', 'ai': True, 'api_key': 'sk-test-secret'}
        self.token = provider.configure(self.config)

    def tearDown(self):
        provider.SETTINGS.reset(self.token)

    def test_secret_removed_and_only_speech_required(self):
        self.assertNotIn('api_key', self.config)
        self.assertTrue(provider.ready({'speech': True, 'ready': False}))
        self.assertEqual(provider.model_id('gemma3:4b'), 'openai/gpt-4.1')
        with self.assertRaises(ValueError):
            provider.configure({'provider': 'openai', 'ai': True})

    def test_routing_images_and_schema_without_local_call(self):
        schema = {'type': 'object', 'properties': {'frame': {'type': 'integer'}}, 'required': ['frame'], 'additionalProperties': False}
        response = {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': '{"frame":2}'}]}]}
        with patch('ai_provider.request', return_value=response) as request, patch('analysis_local.ollama') as local:
            answer = analysis_local.chat([{'role': 'user', 'content': 'JSON : choisis une image'}], Runner(), {}, 'vision', images=['abc']*8, schema=schema)
            self.assertEqual(answer, {'frame': 2})
            local.assert_not_called()
            path, payload = request.call_args.args
            self.assertEqual(path, 'responses')
            self.assertFalse(payload['store'])
            self.assertEqual(len(payload['input'][0]['content']), 9)
            self.assertTrue(payload['text']['format']['strict'])
            self.assertNotIn('sk-test-secret', json.dumps(payload))

    def test_incomplete_and_refusal_never_publish(self):
        for response in [{'status': 'incomplete'}, {'status': 'completed', 'output': [{'content': [{'type': 'refusal'}]}]}]:
            with patch('ai_provider.request', return_value=response), self.assertRaises(ValueError):
                provider.chat([{'role': 'user', 'content': 'JSON'}], Runner(), {}, 'titles')

    def test_http_error_body_never_exposes_secret(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=HTTPError('https://api.openai.com', 401, 'sk-test-secret', {}, None)):
            with self.assertRaises(RuntimeError) as raised:
                provider.request('models/gpt-4.1')
            self.assertNotIn('sk-test-secret', str(raised.exception))
            self.assertIn('401', str(raised.exception))

    def test_local_choice_does_not_use_openai(self):
        token = provider.configure({'provider': 'local'})
        try:
            with patch('ai_provider.request') as network, patch('analysis_local.ollama', return_value={'message': {'content': '{}'}}):
                analysis_local.chat([{'role': 'user', 'content': 'JSON'}], Runner(), {}, 'titles')
                network.assert_not_called()
                self.assertFalse(provider.ready({'speech': True, 'ready': False}))
        finally:
            provider.SETTINGS.reset(token)

    def test_selected_model_routes_all_stages_and_changes_cache_identity(self):
        for model in ['gpt-4.1-mini', 'gpt-5.4-nano', 'gpt-4.1-mini-2025-04-14']:
            token = provider.configure({'provider': 'openai', 'ai': True, 'api_key': 'sk-test-secret', 'openai_model': model})
            try:
                self.assertEqual(provider.model_id('local'), 'openai/' + model)
                response = {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': '{}'}]}]}
                with patch('ai_provider.request', return_value=response) as request:
                    for stage in ['research', 'titles', 'review', 'vision']:
                        provider.chat([{'role': 'user', 'content': 'JSON'}], Runner(), {}, stage, images=['abc'] if stage == 'vision' else None)
                        payload = request.call_args.args[1]
                        self.assertEqual(payload['model'], model)
                        if model == 'gpt-5.4-nano':
                            self.assertEqual(payload['reasoning'], {'effort': 'none'})
                        else:
                            self.assertNotIn('reasoning', payload)
            finally:
                provider.SETTINGS.reset(token)

    def test_invalid_model_cannot_change_request_destination(self):
        for model in ['', '../models', 'https://example.com', 'model with space']:
            with self.assertRaises(ValueError):
                provider.configure({'provider': 'openai', 'ai': True, 'api_key': 'sk-test-secret', 'openai_model': model})

    def test_luna_preserves_reasoning_with_sufficient_vision_budget(self):
        token = provider.configure({'provider': 'openai', 'ai': True, 'api_key': 'sk-test-secret', 'openai_model': 'gpt-6-luna'})
        try:
            complete = {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': '{"frame":3}'}]}]}
            with patch('ai_provider.request', return_value=complete) as request:
                result = provider.chat([{'role': 'user', 'content': 'JSON'}], Runner(), {}, 'vision', images=['abc'] * 8, tokens=500)
                self.assertEqual(result, {'frame': 3})
                payload = request.call_args.args[1]
                self.assertEqual(payload['model'], 'gpt-6-luna')
                self.assertEqual(payload['reasoning'], {'effort': 'medium'})
                self.assertEqual(payload['max_output_tokens'], 16384)
        finally:
            provider.SETTINGS.reset(token)

    def test_token_limit_retries_once_and_accounts_for_both_calls(self):
        incomplete = {'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}, 'output': [{'content': [{'type': 'output_text', 'text': '{"bad":'}]}], 'usage': {'input_tokens': 100, 'output_tokens': 2048, 'output_tokens_details': {'reasoning_tokens': 1900}}}
        complete = {'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': '{"frame":2}'}]}], 'usage': {'input_tokens': 100, 'output_tokens': 900}}
        budgets = []
        def request(path, payload):
            budgets.append(payload['max_output_tokens'])
            return incomplete if len(budgets) == 1 else complete
        timings = {}
        with patch('ai_provider.request', side_effect=request):
            result = provider.chat([{'role': 'user', 'content': 'JSON'}], Runner(), timings, 'vision', tokens=500)
        self.assertEqual(budgets, [2048, 4096])
        self.assertEqual(result, {'frame': 2})
        self.assertEqual(timings['vision_output_tokens'], 2948)
        self.assertEqual(timings['vision_reasoning_tokens'], 1900)

    def test_token_limit_is_bounded_and_filter_is_not_retried(self):
        for reason, calls in [('max_output_tokens', 2), ('content_filter', 1)]:
            incomplete = {'status': 'incomplete', 'incomplete_details': {'reason': reason}}
            with patch('ai_provider.request', return_value=incomplete) as request:
                with self.assertRaises(ValueError) as raised:
                    provider.chat([{'role': 'user', 'content': 'JSON'}], Runner(), {}, 'titles')
                self.assertEqual(request.call_count, calls)
                self.assertIn('tronquée' if calls == 2 else 'filtrage', str(raised.exception))


if __name__ == '__main__':
    unittest.main()
