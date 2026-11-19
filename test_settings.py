"""Isolated settings and transport tests with synthetic credentials and responses."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from serve import create_app
from chat_gateway import Provider
from test_review import request

BASE = '/api/chat/settings'
FAKE = 'test-fixture-only'
LOCAL = {'provider': 'custom', 'base_url': 'http://127.0.0.1:19473/v1', 'model': 'test-local'}


class SettingsTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.db = Path(folder) / 'settings.sqlite3'
        self.local = Provider(profile='ollama', base='http://127.0.0.1:11434', model='test-local')
        self.app = create_app(self.db, chat_provider=self.local)

    def test_test_save_and_secret_lifetime(self):
        cloud = dict(provider='custom', base_url='https://fixture.invalid/v1', model='test-cloud', api_key=FAKE)
        response = {'choices':[{'message':{'content':'OK'}}]}
        with patch('chat_gateway.exchange', return_value=response) as upstream:
            code, result = request(self.app, 'POST', BASE+'/test', cloud)
            self.assertEqual((code, result['source'], result['ok']), (200, 'live', True))
            self.assertEqual(upstream.call_args.kwargs['auth'], FAKE)
            self.assertEqual(len(upstream.call_args.kwargs['body']['messages']), 1)
            self.assertEqual(request(self.app,'GET',BASE)[1]['active']['provider'],'ollama')
            upstream.reset_mock()
            code, data = request(self.app,'POST',BASE,cloud)
            self.assertEqual((code,data['active']['has_key']), (200,True))
            self.assertNotIn(FAKE,json.dumps(data))
            self.assertNotIn('source',data)
            upstream.assert_not_called()
            code, result = request(self.app,'POST',BASE,{**cloud,'api_key':'','model':'new-id'})
            self.assertEqual((code,result['active']['key_source']), (200,'memory'))
            self.assertEqual(request(self.app,'POST',BASE,{**cloud,'base_url':'https://second.invalid/v1','api_key':''})[0],422)
            self.assertNotIn(FAKE,self.db.read_bytes().decode('latin1'))
            restarted=create_app(self.db,chat_provider=self.local)
            after=request(restarted,'GET',BASE)[1]['active']
            self.assertEqual((after['provider'],after['model'],after['has_key'],after['configured']),('custom','new-id',False,False))

    def test_failed_tests_and_origin_checks(self):
        with patch('chat_gateway.exchange',return_value={'choices':[]}) as upstream:
            self.assertEqual(request(self.app,'POST',BASE+'/test',LOCAL)[0],502)
            self.assertEqual(request(self.app,'POST',BASE+'/test',LOCAL,origin='https://example.invalid')[0],403)
            self.assertEqual(upstream.call_count,1)
        invalid = [
            {**LOCAL,'base_url':'http://fixture.invalid/v1'},
            {**LOCAL,'base_url':'https://unit.invalid/v1/chat/completions'},
            {**LOCAL,'base_url':'https://somebody:sample@fixture.invalid/v1'},
            {**LOCAL,'provider':'openai'}, {**LOCAL,'model':'a b'},
            {**LOCAL,'provider':'ollama','base_url':'https://fixture.invalid/v1'},
            {**LOCAL,'provider':'unknown'}
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                code,res=request(self.app,'POST',BASE,{**payload,'api_key':FAKE})
                self.assertEqual(code,422)
                self.assertNotIn(FAKE,str(res))

    def test_all_presets_accept_current_catalog_model(self):
        data=request(self.app,'GET',BASE)[1]
        for row in data['providers']:
            if row['id'] in {'ollama','custom'}:
                continue
            config=dict(provider=row['id'],base_url=row['base_url'],model=row['models'][0],api_key=FAKE)
            with self.subTest(provider=row['id']), patch('chat_gateway.exchange',return_value={'choices':[{'message':{'content':'OK'}}]}) as outgoing:
                self.assertEqual(request(self.app,'POST',BASE+'/test',config)[0],200)
                self.assertEqual(outgoing.call_args.args[0],row['base_url'].rstrip('/')+'/chat/completions')
                self.assertEqual(outgoing.call_args.kwargs['body']['model'],row['models'][0])

    def test_save_switches_real_chat_target_without_reviving_old_context(self):
        with patch('chat_gateway.exchange', return_value={'choices':[{'message':{'content':'OK'}}]}) as upstream:
            self.assertEqual(request(self.app,'POST',BASE,LOCAL)[0],200)
            code, first=request(self.app,'POST','/api/chat',{'role':'assistant','message':'测试'})
            self.assertEqual(code,200)
            self.assertEqual(upstream.call_args.args[0], LOCAL['base_url']+'/chat/completions')
            self.assertEqual(request(self.app,'POST',BASE,{**LOCAL,'model':'next'})[0],200)
            upstream.reset_mock()
            code,_=request(self.app,'POST','/api/chat',{'role':'assistant','message':'续问','conversation_id':first['conversation_id']})
            self.assertEqual(code,410)
            upstream.assert_not_called()


if __name__ == '__main__':
    unittest.main()
