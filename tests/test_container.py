import unittest

from model import Container


class TestContainer(unittest.TestCase):

    def setUp(self):
        self.container1 = Container(NAME="Container1", LENGTH=(100, 200), CPU=(1.0, 2.0), RAM=(512, 1024), GPU=None)
        self.container2 = Container(NAME="Container2", LENGTH=(100, 200), CPU=(1.0, 2.0), RAM=(512, 1024), GPU=None)

    def test_hash(self):
        self.assertEqual(self.container1.__hash__(), id(self.container1))

    def test_eq(self):
        # Two different containers should not be equal
        self.assertNotEqual(self.container1, self.container2)

        # A container should be equal to itself
        self.assertEqual(self.container1, self.container1)


if __name__ == '__main__':
    unittest.main()
