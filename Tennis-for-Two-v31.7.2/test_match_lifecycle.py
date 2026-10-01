"""Regression checks for v31.7.2 without external networking or user saves."""
import os
os.environ.setdefault('SDL_VIDEODRIVER','dummy')
os.environ.setdefault('SDL_AUDIODRIVER','dummy')
import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch, Mock
import pygame
import rollback
from game import initial_world, reset_round, step_world, state_hash, InputState, NEUTRAL_INPUT
from config import FIXED_DT, PROTOCOL_VERSION

class Peer:
    def __init__(self, clock, delay):
        self.clock,self.delay=clock,delay
        self.inbox,self.sent=[],[]
        self.alive,self.error_reason=True,''
        self.other=None
    def send(self,payload):
        self.sent.append(dict(payload))
        self.other.inbox.append((self.clock.now+self.delay,dict(payload)))
        return True
    def poll_all(self):
        ready=[m for t,m in self.inbox if t<=self.clock.now]
        self.inbox=[(t,m) for t,m in self.inbox if t>self.clock.now]
        return ready
    def fail(self,reason):self.alive=False;self.error_reason=reason

class NetworkLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.clock=SimpleNamespace(now=0.)
        self.tp=patch.object(rollback,'time',SimpleNamespace(monotonic=lambda:self.clock.now));self.tp.start()
        self.dp=patch.object(rollback,'NetDiagnostics',return_value=None);self.dp.start()
    def tearDown(self):self.dp.stop();self.tp.stop()
    def pair(self,delay):
        self.clock.now=0.
        p,q=Peer(self.clock,delay),Peer(self.clock,delay);p.other,q.other=q,p
        return rollback.RollbackSession(1,p,True),rollback.RollbackSession(2,q,False),p,q
    def tick(self,h,g,a=NEUTRAL_INPUT,b=NEUTRAL_INPUT):
        h.advance(a);g.advance(b);self.clock.now+=FIXED_DT
    def await_start(self,h,g,generation=0):
        for _ in range(2000):
            if h.started and g.started and h.match_id==g.match_id==generation:return
            self.tick(h,g)
        self.fail('Both peers did not start: '+h.handshake_stage+' / '+g.handshake_stage)
    def test_held_input_rematches_sync_for_either_or_both_players(self):
        for delay in [0,.05,.215]:
            for requester in ['host','guest','both']:
                with self.subTest(rtt=delay*2000,requester=requester):
                    h,g,p,q=self.pair(delay);self.await_start(h,g)
                    for _ in range(800):self.tick(h,g,InputState(right=True),InputState(left=True))
                    h.state.winner=g.state.winner=1
                    if requester in ['guest','both']:g.request_restart()
                    if requester in ['host','both']:h.request_restart()
                    for _ in range(2000):
                        self.tick(h,g,InputState(right=True),InputState(left=True))
                        if h.started and g.started and h.match_id==g.match_id==1:break
                    self.assertTrue(h.started and g.started)
                    self.assertEqual((h.match_id,g.match_id),(1,1))
                    self.assertLessEqual(abs(h.actual_start_at-g.actual_start_at),FIXED_DT*2.01)
                    for _ in range(180):self.tick(h,g,InputState(right=True),InputState(left=True))
                    f=min(h.current_frame,g.current_frame)-70
                    self.assertEqual(state_hash(h.history[f]),state_hash(g.history[f]))
                    self.assertGreater(h.history[f].p1.x,250)
                    self.assertLess(h.history[f].p2.x,750)
                    for peer in [p,q]:self.assertTrue(any(m.get('match_id')==1 and m['type']=='input' for m in peer.sent))
    def test_previous_match_messages_cannot_mutate_rematch(self):
        h,g,p,q=self.pair(0);self.await_start(h,g);h.request_restart();self.await_start(h,g,1)
        for _ in range(20):self.tick(h,g)
        p.send({'type':'input','match_id':0,'player':1,'frame':g.current_frame+8,'bits':2})
        p.send({'type':'state','match_id':0,'frame':0,'state':initial_world().canonical_dict()})
        p.send({'type':'session_exit','match_id':0});p.send({'type':'rematch','match_id':1})
        q.send({'type':'restart_request','match_id':0})
        for _ in range(50):self.tick(h,g)
        self.assertEqual((h.match_id,g.match_id),(1,1));self.assertFalse(g.remote_session_exit)
        self.assertEqual(g.correction_count,0);self.assertEqual(g.state.p1.x,250)
    def test_protocol_mismatch_is_rejected(self):
        h,g,p,q=self.pair(0);p.inbox.clear()
        q.send({'type':'hello','protocol':PROTOCOL_VERSION-1,'role':'guest','player':2,'simulation':rollback.SIMULATION_FINGERPRINT})
        h.process_network();self.assertFalse(p.alive);self.assertIn('Protocol mismatch',p.error_reason)
    def test_exit_during_countdown_reaches_other_peer(self):
        h,g,p,q=self.pair(0)
        for _ in range(20):self.tick(h,g)
        self.assertFalse(h.started);h.request_session_exit();g.process_network()
        self.assertTrue(g.should_leave_online_session)

class StopRender(Exception):pass
class ScreenAndStoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init();pygame.display.set_mode((1000,620));cls.screen=pygame.Surface((1000,620))
        cls.fonts=tuple(pygame.font.Font(None,n) for n in (42,27,17))
    @classmethod
    def tearDownClass(cls):pygame.quit()
    def test_online_victory_screen_renders(self):
        import ui
        s=rollback.RollbackSession(1,None,True);s.state.winner=1;s.state.score1=7
        with patch.object(ui,'RollbackSession',return_value=s),patch.object(ui,'game_events',return_value=[]),patch.object(ui,'present',side_effect=StopRender),patch.object(ui,'SOUND',None):
            with self.assertRaises(StopRender):ui.run_match(self.screen,self.fonts,'host',None,1)
    def test_new_match_key_wins_over_audio_shortcut(self):
        import ui
        s=rollback.RollbackSession(1,None,True);s.state.winner=1
        s.request_match_exit=Mock(side_effect=lambda:setattr(s,'remote_match_exit',True))
        sound=Mock();event=pygame.event.Event(pygame.KEYDOWN,key=pygame.K_n,unicode='n')
        with patch.object(ui,'RollbackSession',return_value=s),patch.object(ui,'game_events',return_value=[event]),patch.object(ui,'SOUND',sound),patch.object(ui,'present',side_effect=AssertionError('Did not leave match')):
            self.assertTrue(ui.run_match(self.screen,self.fonts,'host',None,1))
        s.request_match_exit.assert_called_once();sound.toggle_sfx.assert_not_called()
    def test_n_still_mutes_during_active_match(self):
        import ui
        s=rollback.RollbackSession(1,None,True);event=pygame.event.Event(pygame.KEYDOWN,key=pygame.K_n,unicode='n')
        sound=Mock();sound.toggle_sfx.return_value=True
        with patch.object(ui,'RollbackSession',return_value=s),patch.object(ui,'game_events',return_value=[event]),patch.object(ui,'SOUND',sound),patch.object(ui,'present',side_effect=StopRender):
            with self.assertRaises(StopRender):ui.run_match(self.screen,self.fonts,'host',None,1)
        sound.toggle_sfx.assert_called_once()
    def test_story_win_saved_before_victory_dialogue_exit(self):
        import story
        with TemporaryDirectory() as tmp:
            path=Path(tmp)
            with patch.object(story,'CONFIG_DIR',path),patch.object(story,'STORY_SAVE',path/'story_progress.json'),patch.object(story,'_dialogue',side_effect=[True,False]),patch.object(story,'_play_challenge',return_value=True):
                story._run_chapter(None,None,0,{'unlocked':1,'completed':[]})
                self.assertEqual(story._load_progress(),{'unlocked':2,'completed':[0]})
    def test_default_serve_is_legal_from_both_sides(self):
        for side in [1,2]:
            for frame in [0,431,9999,99999]:
                with self.subTest(side=side,frame=frame):
                    state=initial_world();reset_round(state,side);state.frame=frame
                    for _ in range(31):step_world(state,NEUTRAL_INPUT,NEUTRAL_INPUT)
                    for tick in range(1000):
                        hit=InputState(hit=tick==0)
                        step_world(state,hit if side==1 else NEUTRAL_INPUT,hit if side==2 else NEUTRAL_INPUT)
                        if state.ball.bounces_on_side or state.score1 or state.score2:break
                    self.assertEqual(state.ball.bounce_side,3-side,state.message)
                    self.assertEqual((state.score1,state.score2),(0,0))

if __name__=='__main__':unittest.main()
