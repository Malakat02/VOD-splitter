import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ai_provider
from analysis_local import analyse, cached, digest, save_cache
from core import Runner
from timeline_summary import windows, parts, summarize, compact_evidence, validate
from title_guard import reviewed_candidates


class SummaryTests(unittest.TestCase):
    def test_five_minute_boundaries_and_short_last_period(self):
        segments=[{'start':t,'text':str(t)} for t in [0,299,300,599,600,1278]]
        blocks=windows(segments,1279)
        self.assertEqual([(b['start'],b['end']) for b in blocks],[(0,300),(300,600),(600,900),(900,1200),(1200,1279)])
        self.assertEqual([[i for i,_ in b['segments']] for b in blocks],[[0,1],[2,3],[4],[],[5]])
        self.assertEqual(len(windows([],1200)),4)
        self.assertEqual(len(windows([],1200.04)),4)
        self.assertEqual(windows([{'start':1200,'text':'Dernière parole'}],1200.04)[-1]['segments'][0][0],0)
        self.assertEqual(len(windows([],1201.5)),5)
        for duration in [0,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):windows([],duration)

    def test_long_local_input_has_bounded_parts_without_dropping_words(self):
        text='paroles ' * 10000
        result=parts([(0,{'start':0,'text':text})])
        self.assertGreater(len(result),1)
        self.assertTrue(all(len(p.encode('utf-8')) <= 20000 for p in result))
        self.assertEqual(sum(p.count('paroles') for p in result),text.count('paroles'))

    def test_invalid_or_unproven_summary_is_not_sent_as_full_transcript(self):
        segments=[(0,{'start':0,'text':'Une phrase'}),(2,{'start':310,'text':'Autre période'})]
        with self.assertRaises(ValueError):validate({'summary':'','events':[]},segments)
        result=validate({'summary':'Une décision est envisagée.','events':[{'start_segment':0,'end_segment':2,'event':'Événement','stakes':'','uncertainty':''}]},segments)
        self.assertEqual(result['events'],[])

    def test_local_summary_provider_restored_and_reused_across_api_models(self):
        transcript=[{'start':10,'end':20,'text':'PHRASE_BRUTE_CONFIDENTIELLE : je cherche un moteur.'}]
        token=ai_provider.configure({'provider':'openai','ai':True,'api_key':'sk-test','openai_model':'gpt-4.1'})
        try:
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp); calls=[]
                def local_chat(messages,runner,timings,stage,**kwargs):
                    self.assertFalse(ai_provider.remote())
                    self.assertIn('PHRASE_BRUTE_CONFIDENTIELLE',messages[1]['content'])
                    calls.append(stage)
                    return {'summary':'Le joueur cherche un moteur pour réparer sa voiture.',
                            'events':[{'start_segment':0,'end_segment':0,'event':'Recherche de moteur','stakes':'Réparer la voiture','uncertainty':'Aucun moteur trouvé à ce stade'}]}
                notes,timeline=summarize(transcript,301,folder,'Jeu imposé',Runner(),{},local_chat,digest,cached,save_cache)
                self.assertTrue(ai_provider.remote())
                self.assertEqual(ai_provider.selected_model(),'gpt-4.1')
                other=ai_provider.configure({'provider':'openai','ai':True,'api_key':'sk-test','openai_model':'gpt-4.1-mini'})
                try:
                    summarize(transcript,301,folder,'Jeu imposé',Runner(),{},local_chat,digest,cached,save_cache)
                    self.assertEqual(len(calls),2)
                finally:ai_provider.SETTINGS.reset(other)
                self.assertEqual(len(timeline),2)
                self.assertNotIn('PHRASE_BRUTE_CONFIDENTIELLE',json.dumps(compact_evidence(notes)))
                self.assertIn('PHRASE_BRUTE_CONFIDENTIELLE',notes[0]['source_quote'])
                for name in ['resume_5min.txt','resume_5min.json','transcription.txt']:
                    self.assertNotIn('PHRASE_BRUTE_CONFIDENTIELLE',(folder/name).read_text(encoding='utf-8'))
                transcript[0]['text']+=' La voiture repart.'
                summarize(transcript,301,folder,'Jeu imposé',Runner(),{},local_chat,digest,cached,save_cache)
                self.assertEqual(len(calls),4)
        finally:ai_provider.SETTINGS.reset(token)

    def test_failed_summary_restores_api_settings(self):
        token=ai_provider.configure({'provider':'openai','ai':True,'api_key':'sk-test'})
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    summarize([{'start':0,'text':'Des paroles'}],10,Path(tmp),'jeu',Runner(),{},
                              lambda *args,**kwargs:{'summary':'','events':[]},digest,cached,save_cache)
                self.assertTrue(ai_provider.remote())
                self.assertEqual(ai_provider.SETTINGS.get()['key'],'sk-test')
        finally:ai_provider.SETTINGS.reset(token)

    def test_silent_period_needs_no_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            def no_call(*args,**kwargs):raise AssertionError('Pas d’inférence pour le silence')
            notes,timeline=summarize([],600,Path(tmp),'jeu',Runner(),{},no_call,digest,cached,save_cache)
            self.assertEqual(len(timeline),2)
            self.assertTrue(all(not b['events'] for b in timeline))

    def test_verbatim_does_not_reach_title_or_review_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);clip=folder/'clip.mp4';clip.write_bytes(b'test')
            (folder/'transcription.json').write_text(json.dumps([{'start':1,'end':3,'text':'PHRASE_BRUTE_UNIQUE Je cherche une roue'}]),encoding='utf-8')
            frames=[]
            for i in range(8):
                path=folder/f'{i}.jpg';path.write_bytes(bytes([i]));frames.append({'path':path})
            stages=[]
            def fake_chat(messages,runner,timings,stage,**kwargs):
                stages.append(stage)
                if stage.startswith('resume'):
                    return {'summary':'Le joueur cherche une roue après une panne.', 'events':[{'start_segment':0,'end_segment':0,'event':'Recherche de roue','stakes':'Réparer le véhicule','uncertainty':''}]}
                self.assertNotIn('PHRASE_BRUTE_UNIQUE',json.dumps(messages))
                self.assertNotIn('source_quote',json.dumps(messages))
                if stage=='vision':return {'frame':1,'description':'Une voiture'}
                if stage.startswith('titles'):
                    return {'candidates':[{'title':t,'moment_id':1,'reason':'Recherche de roue','thumbnail_text':'Où est ma roue'} for t in ['Je cherche ma roue après la panne','On cherche une roue pour repartir','Une roue manque pour repartir']],'summary':'Recherche de roue.'}
                return {'scope_game':'Mon jeu','best':[0,1,2],'judgments':[{'index':i,'scope_ok':True,'grounded':True,'catchy':True} for i in range(3)]}
            with patch('analysis_local.chat',side_effect=fake_chat):
                result=analyse(clip,{'duration':10,'audio':True},folder,frames,None,Runner(),{'game':'Mon jeu'},reuse_legacy=True)
            self.assertEqual(result['summary_minutes'],5)
            self.assertEqual(result['summary_metrics']['provider'],'local')
            self.assertNotIn('PHRASE_BRUTE_UNIQUE',json.dumps(result))
            self.assertIn('titles_0',stages)
            self.assertIn('review_0',stages)

    def test_statistic_guard_still_uses_local_source(self):
        data={'candidates':[{'title':'Je gagne 90 % de survie','moment_id':1}]}
        review={'scope_game':'Mon jeu','best':[0],'judgments':[{'index':0,'scope_ok':True,'grounded':True,'catchy':True}]}
        notes=[{'id':1,'quote':'Il gagne 90 % de survie','source_quote':'Ce sacrifice donne 90 % de dévotion'}]
        with self.assertRaises(ValueError):reviewed_candidates(data,review,'Mon jeu',notes,min_count=1)
    def test_invented_major_outcome_cannot_survive_in_summary(self):
        value={'summary':'Le moteur surchauffe et la sauvegarde est corrompue.', 'events':[
            {'start_segment':0,'end_segment':0,'event':'Le moteur surchauffe.','stakes':'La voiture est immobilisée','uncertainty':''},
            {'start_segment':1,'end_segment':1,'event':'Le joueur cherche une portière.','stakes':'Équiper la voiture','uncertainty':''}]}
        result=validate(value,[(0,{'text':'Il y a de l’eau dans le moteur ?'}),(1,{'text':'Je cherche une portière'})])
        self.assertEqual(len(result['events']),1)
        self.assertNotIn('surchauffe',result['summary'])
        self.assertNotIn('corrompue',result['summary'])


if __name__=='__main__':unittest.main()
