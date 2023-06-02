import unittest

from model import Vm
from policy.os import OsTimeShared


class TestVm(unittest.TestCase):
    def setUp(self):
        # Create test objects or variables if needed
        self.vm = Vm(NAME="TestVM", CPU=4, RAM=8, GPU=(2, 4), OS=OsTimeShared)

    def test_turn_on(self):
        # Test turn_on method
        self.vm.turn_on()
        self.assertTrue(self.vm.is_on())

    def test_turn_off(self):
        # Test turn_off method
        self.vm.turn_on()  # Make sure the VM is turned on before turning it off
        self.vm.turn_off()
        self.assertTrue(self.vm.is_off())

    # Add more test cases as needed


if __name__ == '__main__':
    unittest.main()
