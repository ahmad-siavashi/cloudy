import unittest

from model import App


class TestApp(unittest.TestCase):

    def setUp(self):
        self.app = App(NAME="TestApp", LENGTH=(100, 200))

    def test_post_init(self):
        self.assertEqual(self.app._remained, [100, 200])

    def test_has_resumed_once(self):
        self.assertFalse(self.app.has_resumed_once())
        self.app.resume((50, 50))
        self.assertTrue(self.app.has_resumed_once())

    def test_restart(self):
        self.app.resume((50, 50))
        self.app.restart()
        self.assertEqual(self.app._remained, [100, 200])

    def test_resume(self):
        consumed = self.app.resume((50, 50))
        self.assertEqual(consumed, [50, 50])
        self.assertEqual(self.app._remained, [50, 150])

    def test_is_stopped(self):
        self.assertFalse(self.app.is_stopped())
        self.app.resume((100, 200))
        self.assertTrue(self.app.is_stopped())


if __name__ == '__main__':
    unittest.main()
