from __future__ import annotations
import unittest
from fastapi.testclient import TestClient
from logiroute.api import create_app


class TestDispatchAPI(unittest.TestCase):
    def test_malformed_decimal_and_boolean_seed_rejected(self) -> None:
        first=self.snapshot['orders'][0]
        response=self.command('add',id='invalid-decimal',destination=first['destination'],demand='broken',earliest=0,deadline=2000,priority='urgent')
        self.assertEqual(response.status_code,422)
        response=self.client.post('/api/v2/sessions',json={'seed':True})
        self.assertEqual(response.status_code,422)

    def setUp(self) -> None:
        self.context=TestClient(create_app()); self.client=self.context.__enter__()
        self.addCleanup(self.context.__exit__,None,None,None)
        response=self.client.post('/api/v2/sessions',json={'seed':42})
        self.assertEqual(response.status_code,200,response.text); self.snapshot=response.json(); self.key=self.snapshot['id']

    def command(self,command: str,**values):
        response=self.client.post(f'/api/v2/sessions/{self.key}/commands',json={'revision':self.snapshot['revision'],'command':command,**values})
        if response.status_code==200: self.snapshot=response.json()
        return response

    def test_plan_execute_and_compare_same_input(self) -> None:
        response=self.command('compare'); self.assertEqual(response.status_code,200,response.text)
        comparison=self.snapshot['comparison']; self.assertEqual(comparison[0]['fingerprint'],comparison[1]['fingerprint'])
        self.assertTrue(all(p['report']['complete_all'] for p in comparison))
        self.assertEqual(self.command('plan',objective='cost').status_code,200)
        self.assertEqual(self.command('depart').status_code,200)
        while self.snapshot['running']: self.assertEqual(self.command('step').status_code,200)
        self.assertTrue(self.snapshot['audit']['complete_all'])
        self.assertTrue(all(o['status']=='delivered' for o in self.snapshot['orders']))

    def test_exact_json_decimal_and_stale_transaction(self) -> None:
        rev=self.snapshot['revision']; dest=self.snapshot['orders'][0]['destination']
        body='{"revision":'+str(rev)+',"command":"add","id":"precise","destination":"'+dest+'","demand":0.10000000000000000000000000001,"earliest":0,"deadline":2000,"priority":"critical"}'
        response=self.client.post(f'/api/v2/sessions/{self.key}/commands',content=body,headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code,200,response.text)
        order=next(o for o in response.json()['orders'] if o['id']=='precise')
        self.assertEqual(order['demand'],'0.10000000000000000000000000001')
        self.snapshot=response.json()
        response=self.command('add',id='string-quantity',destination=dest,demand='0.20000000000000000000000000001',earliest=0,deadline=2000,priority='urgent')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(next(o for o in response.json()['orders'] if o['id']=='string-quantity')['demand'],'0.20000000000000000000000000001')
        stale=self.client.post(f'/api/v2/sessions/{self.key}/commands',json={'revision':rev,'command':'plan'})
        self.assertEqual(stale.status_code,409)

    def test_invalid_input_atomic_and_legacy_available(self) -> None:
        before=self.snapshot['revision']
        response=self.command('add',id='bad',destination='missing',demand=-1,earliest=0,deadline=1,priority='normal')
        self.assertEqual(response.status_code,422,response.text)
        current=self.client.get(f'/api/v2/sessions/{self.key}').json()
        self.assertEqual(current['revision'],before)
        self.assertEqual(self.client.get('/api/health').status_code,200)
        self.assertEqual(self.client.get('/api/v2/sessions/missing').status_code,404)

    def test_automatic_pause_traffic_and_input_validation(self) -> None:
        self.assertEqual(self.command('automatic',count=2,seed=100,priority='urgent').status_code,200)
        self.assertEqual(len(self.snapshot['orders']),14)
        self.assertEqual(self.command('plan').status_code,200)
        self.assertEqual(self.command('depart').status_code,200)
        self.assertEqual(self.command('plan').status_code,409)
        self.assertEqual(self.command('pause').status_code,200)
        while self.snapshot['running']: self.assertEqual(self.command('step').status_code,200)
        edge=self.snapshot['edges'][0]
        self.assertEqual(self.command('traffic',source=edge['source'],target=edge['target'],status='moderate').status_code,200)
        self.assertEqual(self.snapshot['traffic_version'],1)
        before=self.snapshot['revision']
        response=self.client.post(f'/api/v2/sessions/{self.key}/commands',content='{"revision":0,"revision":1,"command":"step"}')
        self.assertEqual(response.status_code,422)
        self.assertEqual(self.client.get(f'/api/v2/sessions/{self.key}').json()['revision'],before)
