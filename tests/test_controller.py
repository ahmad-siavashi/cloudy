import unittest

from model import Controller, Vm
from policy.control_plane import ControlPlaneRoundRobin
from policy.os import OsTimeShared


class TestController(unittest.TestCase):

    def setUp(self):
        self.vm1 = Vm(NAME="VM1", CPU=2, RAM=1024, GPU=None, OS=OsTimeShared)
        self.vm2 = Vm(NAME="VM2", CPU=2, RAM=1024, GPU=None, OS=OsTimeShared)
        self.controller = Controller(NAME='controller', LENGTH=(10, 10), NODES=[self.vm1, self.vm2],
                                     CONTROL_PLANE=ControlPlaneRoundRobin)

    def test_post_init(self):
        # Assuming the controller initializes worker apps on nodes
        self.assertTrue(any(app.NAME == 'worker' for app in self.vm1.OS))
        self.assertTrue(any(app.NAME == 'worker' for app in self.vm2.OS))

    def test_resume(self):
        consumed_cycles = self.controller.resume(cpu=(2, 2))
        # Assuming the controller equally distributes the cycles to its nodes
        self.assertEqual(consumed_cycles, [2, 2])

    def test_is_stopped(self):
        # Initially, the controller should not be stopped
        self.assertFalse(self.controller.is_stopped())
        # After resuming with enough cycles, it should be stopped
        self.controller.resume(cpu=(1000, 1000))
        self.assertTrue(self.controller.is_stopped())


if __name__ == '__main__':
    unittest.main()
