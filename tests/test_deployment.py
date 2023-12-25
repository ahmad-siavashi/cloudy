import unittest

from model import Deployment


class TestDeployment(unittest.TestCase):

    def setUp(self):
        container_spec_1 = {
            "NAME": "WebServer",
            "LENGTH": (1000, 1500),
            "CPU": (1.0, 2.0),
            "RAM": (512, 1024),
            "GPU": None
        }

        container_spec_2 = {
            "NAME": "Database",
            "LENGTH": (2000, 2500),
            "CPU": (0.5, 1.5),
            "RAM": (256, 512),
            "GPU": (1, 2)
        }

        self.container_specs = [container_spec_1, container_spec_2]
        self.deployment = Deployment(NAME="MyDeployment", replicas=3, CONTAINER_SPECS=self.container_specs)

    def test_iter(self):
        containers = list(self.deployment)
        self.assertEqual(len(containers), 2)
        self.assertIsInstance(containers[0], dict)
        self.assertIsInstance(containers[1], dict)

    def test_hash(self):
        self.assertEqual(self.deployment.__hash__(), id(self.deployment))

    def test_eq(self):
        deployment2 = Deployment(NAME="MyDeployment2", replicas=3, CONTAINER_SPECS=self.container_specs[:1])
        self.assertNotEqual(self.deployment, deployment2)
        self.assertEqual(self.deployment, self.deployment)


if __name__ == '__main__':
    unittest.main()
