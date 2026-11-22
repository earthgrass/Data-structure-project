from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from logiroute.api import create_app


class TestDispatchOrderReplan(unittest.TestCase):
    def setUp(self) -> None:
        self.context=TestClient(create_app());self.client=self.context.__enter__()
        self.addCleanup(self.context.__exit__,None,None,None)
        r=self.client.post('/api/v2/sessions',json={'seed':42})
        self.assertEqual(r.status_code,200,r.text);self.snapshot=r.json();self.key=self.snapshot['id']

    def command(self,kind: str,**fields: object):
        r=self.client.post('/api/v2/sessions/'+self.key+'/commands',json={'revision':self.snapshot['revision'],'command':kind,**fields})
        if r.status_code==200:self.snapshot=r.json()
        return r

    def ok(self,kind: str,**fields: object) -> dict:
        r=self.command(kind,**fields);self.assertEqual(r.status_code,200,r.text);return self.snapshot

    def add(self,key: str,**fields: object) -> dict:
        first=self.snapshot['orders'][0]
        return self.ok('add',id=key,destination=first['destination'],demand='0.10000000000000000000000000001',earliest=self.snapshot['now'],deadline=self.snapshot['now']+2000,priority='urgent',**fields)

    def moving(self) -> dict:
        self.ok('plan',objective='distance');self.ok('depart')
        while not any(v['current'] and v['current']['kind']=='drive' for v in self.snapshot['vehicles']):self.ok('step')
        return self.snapshot

    def test_new_order_stops_at_checkpoint_without_teleport_or_cargo_reset(self) -> None:
        before=self.moving();old_plan=before['plan']['fingerprint'];old_events=before['events']
        entered={v['id']:v['current'] for v in before['vehicles'] if v['current'] and v['current']['kind'] not in ('wait','finish')}
        cargo={v['id']:(v['position'],v['load'],v['cargo']) for v in before['vehicles']}
        self.add('INSERTED',auto_replan=True)
        self.assertEqual(self.snapshot['order_control']['status'],'waiting_checkpoint')
        self.assertTrue(self.snapshot['needs_replan']);self.assertFalse(self.snapshot['ready'])
        self.assertEqual(self.snapshot['plan']['fingerprint'],old_plan)
        self.assertEqual(cargo,{v['id']:(v['position'],v['load'],v['cargo']) for v in self.snapshot['vehicles']})
        self.assertEqual(old_events,self.snapshot['events'][:len(old_events)])
        self.assertEqual(next(o for o in self.snapshot['orders'] if o['id']=='INSERTED')['demand'],'0.10000000000000000000000000001')
        while self.snapshot['running']:self.ok('step')
        self.assertEqual(self.snapshot['order_control']['status'],'applied')
        self.assertTrue(self.snapshot['ready']);self.assertFalse(self.snapshot['running'])
        self.assertTrue(self.snapshot['plan']['report']['safe_to_apply']);self.assertTrue(self.snapshot['audit']['valid'])
        self.assertEqual(self.snapshot['order_control']['planned_order_version'],self.snapshot['order_control']['order_version'])
        for v in self.snapshot['vehicles']:
            if v['id'] in entered and entered[v['id']]['kind']=='drive':self.assertEqual(v['position'],entered[v['id']]['target'])
        new_actions=[e['action'] for e in self.snapshot['events'][len(old_events):] if e['kind']=='action']
        self.assertEqual(new_actions,list(entered.values()))
        self.assertEqual(next(o for o in self.snapshot['orders'] if o['id']=='INSERTED')['location'][0],'warehouse')
        self.assertIn('INSERTED',self.snapshot['plan']['accepted'])

    def test_checkpoint_add_and_cancel_replan_without_departing_and_keep_identity(self) -> None:
        self.ok('plan',objective='cost');first=self.snapshot['orders'][0]['id']
        self.add('SAME_SITE',auto_replan=True)
        self.assertIn(first,self.snapshot['plan']['accepted']);self.assertIn('SAME_SITE',self.snapshot['plan']['accepted'])
        version=self.snapshot['order_control']['order_version']
        self.ok('cancel',id='SAME_SITE')
        self.assertEqual(self.snapshot['order_control']['order_version'],version+1)
        self.assertEqual(self.snapshot['order_control']['status'],'applied')
        self.assertTrue(self.snapshot['ready']);self.assertFalse(self.snapshot['running'])
        self.assertNotIn('SAME_SITE',self.snapshot['plan']['accepted']);self.assertIn(first,self.snapshot['plan']['accepted'])
        self.assertEqual(next(o for o in self.snapshot['orders'] if o['id']=='SAME_SITE')['status'],'cancelled')
        self.assertTrue(any(e['kind']=='cancel' and e['id']=='SAME_SITE' for e in self.snapshot['events']))
        before=self.snapshot
        self.assertEqual(self.command('add',id='SAME_SITE',destination=before['orders'][0]['destination'],demand=1,earliest=0,deadline=2000,priority='urgent').status_code,422)
        self.assertEqual(self.client.get('/api/v2/sessions/'+self.key).json(),before)

    def test_illegal_loaded_cancellation_does_not_enable_or_mutate_control(self) -> None:
        self.moving();loaded=next(o['id'] for o in self.snapshot['orders'] if o['location'][0]=='vehicle');before=self.snapshot
        self.assertEqual(self.command('cancel',id=loaded,auto_replan=True).status_code,409)
        self.assertEqual(self.client.get('/api/v2/sessions/'+self.key).json(),before)

    def test_create_opt_in_expiry_priority_and_batch_orders_are_versioned(self) -> None:
        r=self.client.post('/api/v2/sessions',json={'seed':1,'auto_replan':True})
        self.assertEqual(r.status_code,200,r.text);self.snapshot=r.json();self.key=self.snapshot['id']
        self.assertTrue(self.snapshot['order_control']['enabled']);self.assertEqual(self.snapshot['order_control']['status'],'idle')
        self.ok('automatic',count=2,seed=100,priority='urgent')
        version=self.snapshot['order_control']['order_version'];self.assertGreater(version,0)
        self.assertEqual(self.snapshot['order_control']['change_kind'],'automatic')
        oid=self.snapshot['orders'][0]['id'];self.ok('priority',id=oid,priority='critical')
        self.assertEqual(self.snapshot['order_control']['order_version'],version+1)
        self.ok('expire',id=oid)
        self.assertEqual(self.snapshot['order_control']['order_version'],version+2)
        self.assertEqual(next(o for o in self.snapshot['orders'] if o['id']==oid)['status'],'expired')
        self.assertEqual(self.snapshot['order_control']['planned_order_version'],version+2)

    def test_legacy_add_still_requires_explicit_plan_and_opt_in_must_be_boolean(self) -> None:
        self.ok('plan');fingerprint=self.snapshot['plan']['fingerprint'];self.add('LEGACY')
        self.assertEqual(self.snapshot['plan']['fingerprint'],fingerprint)
        self.assertFalse(self.snapshot['order_control']['enabled'])
        before=self.snapshot
        first=before['orders'][0]
        r=self.command('add',id='INVALID',destination=first['destination'],demand=1,earliest=0,deadline=2000,priority='normal',auto_replan='true')
        self.assertEqual(r.status_code,422);self.assertEqual(self.client.get('/api/v2/sessions/'+self.key).json(),before)

    def test_delivery_history_is_retained_without_triggering_order_revision(self) -> None:
        self.add('ADDED',auto_replan=True);version=self.snapshot['order_control']['order_version'];plan_events=len([e for e in self.snapshot['events'] if e['kind']=='plan'])
        self.ok('depart')
        while self.snapshot['running']:self.ok('step')
        self.assertTrue(self.snapshot['audit']['complete_all']);self.assertTrue(self.snapshot['audit']['valid'])
        self.assertTrue(all(o['status']=='delivered' for o in self.snapshot['orders']))
        self.assertEqual(self.snapshot['order_control']['order_version'],version)
        self.assertEqual(len([e for e in self.snapshot['events'] if e['kind']=='plan']),plan_events)
        self.assertEqual(len({oid for e in self.snapshot['events'] if e['kind']=='action' and e['action']['kind']=='deliver' for oid in e['action']['ids']}),len(self.snapshot['orders']))

    def test_impossible_new_order_is_considered_but_not_falsely_accepted(self) -> None:
        self.ok('plan');first=self.snapshot['orders'][0]
        self.ok('add',id='TOO_LATE',destination=first['destination'],demand=1,earliest=0,deadline=0.001,priority='urgent',auto_replan=True)
        self.assertEqual(self.snapshot['order_control']['status'],'applied')
        self.assertTrue(self.snapshot['plan']['report']['safe_to_apply']);self.assertFalse(self.snapshot['plan']['report']['complete_all'])
        self.assertIn('TOO_LATE',dict(self.snapshot['plan']['deferred']));self.assertNotIn('TOO_LATE',self.snapshot['plan']['accepted'])
        self.assertEqual(next(o for o in self.snapshot['orders'] if o['id']=='TOO_LATE')['status'],'pending')
        self.assertEqual(self.snapshot['order_control']['planned_order_version'],self.snapshot['order_control']['order_version'])

    def test_enabled_traffic_uses_same_checkpoint_flow_only_once(self) -> None:
        self.add('ENABLED',auto_replan=True);order_version=self.snapshot['order_control']['order_version']
        self.ok('depart');self.ok('step')
        entered=next(v['current'] for v in self.snapshot['vehicles'] if v['current'] and v['current']['kind']=='drive')
        plans=len([e for e in self.snapshot['events'] if e['kind']=='plan'])
        self.ok('traffic',source=entered['source'],target=entered['target'],status='moderate')
        self.assertEqual(self.snapshot['order_control']['status'],'waiting_checkpoint')
        self.assertEqual(self.snapshot['order_control']['change_kind'],'traffic')
        while self.snapshot['running']:self.ok('step')
        self.assertEqual(self.snapshot['order_control']['status'],'applied')
        self.assertEqual(self.snapshot['order_control']['order_version'],order_version)
        self.assertEqual(len([e for e in self.snapshot['events'] if e['kind']=='plan']),plans+1)
        self.assertEqual(self.snapshot['plan']['traffic_version'],self.snapshot['traffic_version'])
        self.assertTrue(self.snapshot['audit']['valid']);self.assertTrue(self.snapshot['ready'])

    def test_traffic_change_from_legacy_session_replans_even_when_road_clears(self) -> None:
        self.ok('plan');before=self.snapshot
        edge=before['edges'][0];plans=len([e for e in before['events'] if e['kind']=='plan'])
        positions=[(v['id'],v['position'],v['load'],v['cargo']) for v in before['vehicles']]
        for index,status in enumerate(('light','clear'),start=1):
            self.ok('traffic',source=edge['source'],target=edge['target'],status=status,auto_replan=True)
            self.assertTrue(self.snapshot['order_control']['enabled'])
            self.assertEqual(self.snapshot['order_control']['status'],'applied')
            self.assertEqual(self.snapshot['order_control']['change_kind'],'traffic')
            self.assertEqual(self.snapshot['traffic_version'],index)
            self.assertEqual(self.snapshot['plan']['traffic_version'],index)
            self.assertEqual(len([e for e in self.snapshot['events'] if e['kind']=='plan']),plans+index)
            self.assertEqual(self.snapshot['order_control']['order_version'],0)
            self.assertTrue(self.snapshot['plan']['report']['valid'])
            self.assertEqual(positions,[(v['id'],v['position'],v['load'],v['cargo']) for v in self.snapshot['vehicles']])

    def test_unsafe_continuation_keeps_new_order_old_plan_and_actual_cargo(self) -> None:
        self.moving();self.ok('pause')
        while self.snapshot['running']:self.ok('step')
        session=self.context.app.state.dispatch_service.sessions[self.key]
        car=next(k for k in session.state.vehicles if any(loc==('vehicle',k) for loc in session.state.locations.values()))
        at=session.state.positions[car]
        for edge in list(session.state.graph.get_neighbors(at)):session.traffic(*edge.key,'blocked')
        self.snapshot=self.client.get('/api/v2/sessions/'+self.key).json();before=self.snapshot
        self.add('BLOCKED_NEW',auto_replan=True)
        self.assertEqual(self.snapshot['order_control']['status'],'blocked')
        self.assertTrue(self.snapshot['order_control']['reason']);self.assertFalse(self.snapshot['running']);self.assertFalse(self.snapshot['ready'])
        self.assertEqual(self.snapshot['plan'],before['plan']);self.assertEqual(self.snapshot['vehicles'],before['vehicles'])
        self.assertIn('BLOCKED_NEW',[o['id'] for o in self.snapshot['orders']]);self.assertTrue(self.snapshot['audit']['valid'])
        self.assertNotEqual(self.snapshot['order_control']['planned_order_version'],self.snapshot['order_control']['order_version'])
        version=self.snapshot['revision'];self.assertEqual(self.client.get('/api/v2/sessions/'+self.key).json()['revision'],version)
        self.assertEqual(self.command('depart').status_code,409)
        session=self.context.app.state.dispatch_service.sessions[self.key]
        for edge in list(session.state.graph.get_neighbors(at)):session.traffic(*edge.key,'clear')
        self.snapshot=self.client.get('/api/v2/sessions/'+self.key).json()
        self.ok('plan',objective='cost')
        self.assertEqual(self.snapshot['order_control']['status'],'applied');self.assertIsNone(self.snapshot['order_control']['reason'])
        self.assertTrue(self.snapshot['ready']);self.assertIn('BLOCKED_NEW',self.snapshot['plan']['accepted'])
        self.assertFalse(self.snapshot['running']);self.assertTrue(self.snapshot['audit']['valid'])


if __name__=='__main__':unittest.main()
