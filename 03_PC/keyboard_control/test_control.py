"""Offline control/stop tests: no ROS, WSL, serial, or physical movement."""
import math
import unittest
from unittest.mock import patch
from control_state import (ControlState, TRACK_M, MAX_WHEEL, MAX_LINEAR,
                           MAX_ANGULAR, MAX_LINEAR_ACCEL, MAX_ANGULAR_ACCEL)
from keyboard_server import Backend

class ControlTests(unittest.TestCase):
    def setUp(self):
        self.s = ControlState()
        self.s.receive({'type':'arm'}, 0.0, True)

    def command(self, t, v=.2, w=.8):
        self.s.receive(dict(type='command',v=v,w=w),t,True)
        return self.s.output(t,True)

    def test_linear_and_angular_acceleration_with_jitter_and_caps(self):
        t=0.0;old=(0.,0.)
        self.command(t)
        for dt in [.02,.05,.08,.01,.04]*40:
            t+=dt
            new=self.command(t)
            self.assertLessEqual(abs(new[0]-old[0]),MAX_LINEAR_ACCEL*dt+1e-12)
            self.assertLessEqual(abs(new[1]-old[1]),MAX_ANGULAR_ACCEL*dt+1e-12)
            self.assertLessEqual(abs(new[0])+abs(new[1])*TRACK_M/2,MAX_WHEEL+1e-12)
            old=new
        self.assertAlmostEqual(new[1]/new[0],MAX_ANGULAR/MAX_LINEAR)

    def test_same_time_calls_do_not_accelerate(self):
        self.command(0)
        first=self.s.output(.05,True)
        for _ in range(20):self.assertEqual(self.s.output(.05,True),first)

    def test_requires_explicit_arm(self):
        self.s.stop('stop')
        self.command(.05)
        self.assertEqual(self.s.output(.1,True),(0.,0.))

    def test_releasing_all_directions_stops_immediately(self):
        self.command(0);self.command(.1)
        self.assertGreater(self.s.v,0)
        self.assertEqual(self.command(.11,0,0),(0.,0.))
        self.assertEqual((self.s.target_v,self.s.target_w),(0.,0.))

    def test_releasing_turn_stops_turn_without_stopping_forward(self):
        self.command(0);self.command(.1)
        v,w=self.command(.11,.2,0)
        self.assertEqual(w,0.)
        self.assertGreater(v,0.)

    def test_reverse_command_is_ramped_through_zero(self):
        self.command(0,.2,0);self.command(.1,.2,0)
        self.command(.1,-.2,0)
        before=self.s.v
        after=self.s.output(.15,True)[0]
        self.assertGreaterEqual(after,0.)
        self.assertLessEqual(before-after,MAX_LINEAR_ACCEL*.05+1e-12)
        for i in range(4,15):self.command(i*.05,-.2,0)
        self.assertLess(self.s.v,0.)

    def test_stop_cancels_pending_ramp_and_rearm_starts_at_zero(self):
        self.command(0);self.command(.1)
        self.s.receive({'type':'stop'},.11,True)
        self.assertEqual(self.s.output(.12,True),(0.,0.))
        self.assertFalse(self.s.armed)
        self.s.receive({'type':'arm'},.13,True)
        self.assertEqual(self.s.output(.14,True),(0.,0.))

    def test_input_timeout_and_late_packet_cannot_revive_motion(self):
        self.command(0);self.command(.1)
        self.assertEqual(self.s.output(.401,True),(0.,0.))
        self.command(.42)
        self.assertFalse(self.s.armed)
        self.assertEqual(self.s.output(.43,True),(0.,0.))

    def test_feedback_loss_keeps_ramp_but_not_expired_input(self):
        self.command(0)
        self.assertGreater(self.s.output(.1,False)[0],0)
        self.assertEqual(self.s.output(.31,False),(0.,0.))

    def test_nonfinite_and_wrong_types_stop(self):
        for bad in [math.nan,math.inf,-math.inf,'0.1',True,None]:
            self.s.receive({'type':'arm'},0,True)
            self.s.receive(dict(type='command',v=bad,w=0),.01,True)
            self.assertFalse(self.s.armed)
            self.assertEqual(self.s.output(.02,True),(0.,0.))

    def test_long_scheduler_gap_has_bounded_ramp_step(self):
        self.command(0)
        self.assertLessEqual(self.s.output(.2,True)[0],MAX_LINEAR_ACCEL*.1+1e-12)

    def test_old_receive_time_does_not_rewind_ramp_clock(self):
        self.command(0)
        value=self.s.output(.1,True)
        self.command(.09)
        self.assertEqual(self.s.output(.1,True),value)

    def test_preview_never_spawns_process(self):
        with patch('keyboard_server.subprocess.Popen',side_effect=AssertionError('No process allowed')):
            b=Backend(True,'Ubuntu')
            b.send({'type':'arm','seq':1})
            b.send({'type':'command','seq':2,'v':.2,'w':.8})
            status=b.snapshot()
            self.assertGreaterEqual(status['v'],0.)
            self.assertLessEqual(status['v'],.2)
            b.close()

    def test_stale_input_cannot_override_stop(self):
        b=Backend(True,'Ubuntu')
        b.send({'type':'arm','seq':1});b.send({'type':'stop','seq':3})
        self.assertFalse(b.send({'type':'arm','seq':2}))
        self.assertFalse(b.snapshot()['armed'])

    def test_output_zeros_are_floats(self):
        self.assertTrue(all(type(x) is float for x in self.command(.05,0,0)))

if __name__=='__main__':unittest.main()
