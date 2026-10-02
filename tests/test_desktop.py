import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.request
import urllib.error
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
from desktop import DesktopSession, DesktopApi, CloseController


class DesktopTests(unittest.TestCase):
    def test_internal_server_requires_token_and_stops_with_session(self):
        with tempfile.TemporaryDirectory() as tmp,patch('desktop.ROOT',Path(tmp)):
            session = DesktopSession()
            session.start()
            base = session.url.split('#')[0]
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            try:
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    opener.open(base+'api/state',timeout=2)
                self.assertEqual(denied.exception.code,404)
                request = urllib.request.Request(base+'api/state',headers={'X-Vod-Token':app.TOKEN})
                with opener.open(request,timeout=2) as response:
                    self.assertEqual(json.load(response)['version'],9)
                with self.assertRaises(urllib.error.HTTPError) as denied_host:
                    opener.open(urllib.request.Request(base+'api/state',headers={'Host':'foreign.example','X-Vod-Token':app.TOKEN}),timeout=2)
                self.assertEqual(denied_host.exception.code,403)
            finally:
                session.stop()
                app.CANCEL.clear()
            self.assertFalse(session.thread.is_alive())

    def test_native_picker_cancel_selection_and_busy_guard(self):
        api=DesktopApi();api._window=Mock()
        module=SimpleNamespace(FileDialog=SimpleNamespace(OPEN=1,FOLDER=2))
        with patch.dict(sys.modules,{'webview':module}),patch.object(app,'STATE',{'busy':False}):
            api._window.create_file_dialog.return_value=None
            self.assertIsNone(api.choose_path('video'))
            api._window.create_file_dialog.return_value=('C:/Vidéos été/stream.mp4',)
            self.assertEqual(api.choose_path('video'),'C:/Vidéos été/stream.mp4')
            self.assertEqual(api._window.create_file_dialog.call_args.args[0],1)
            api.choose_path('folder')
            self.assertEqual(api._window.create_file_dialog.call_args.args[0],2)
            with self.assertRaises(ValueError):api.choose_path('execute')
        with patch.object(app,'STATE',{'busy':True}):
            with self.assertRaises(ValueError):api.choose_path('video')

    def test_closing_cancel_keeps_job_running_then_waits_before_closing(self):
        window=Mock();finished=threading.Event();window.destroy.side_effect=finished.set
        state={'busy':True,'logs':[]};cancel=threading.Event()
        with patch.object(app,'STATE',state),patch.object(app,'CANCEL',cancel):
            controller=CloseController(window)
            window.create_confirmation_dialog.return_value=False
            self.assertFalse(controller.on_closing())
            self.assertFalse(cancel.is_set())
            window.create_confirmation_dialog.return_value=True
            self.assertFalse(controller.on_closing())
            self.assertTrue(cancel.is_set())
            self.assertFalse(finished.is_set())
            self.assertFalse(controller.on_closing())
            self.assertEqual(window.create_confirmation_dialog.call_count,2)
            state['busy']=False
            self.assertTrue(finished.wait(2))
            self.assertTrue(controller.on_closing())
