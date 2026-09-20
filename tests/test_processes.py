from __future__ import annotations

import unittest

from daiklib.processes import (
    ProcessConfigError,
    process_environment,
    process_secrets,
    redact,
    redact_value,
    select_process,
)


class ProcessEnvironmentTests(unittest.TestCase):
    def config(self):
        return {
            "processes": {
                "broker-domain": {
                    "type": "broker",
                    "env": {"GH_TOKEN": {"from_env": "DAIK_GH_TOKEN", "required": True}},
                },
                "workers": {
                    "type": "agent",
                    "roles": ["implementation", "review"],
                    "env": {
                        "GH_TOKEN": {"from_env": "DAIK_GH_TOKEN", "required": True},
                        "LOG_LEVEL": {"value": "info"},
                    },
                },
                "tests": {
                    "type": "agent",
                    "roles": ["testing"],
                    "env": {
                        "TEST_SERVER_TOKEN": {
                            "from_env": "DAIK_TEST_TOKEN",
                            "required": True,
                        }
                    },
                },
            }
        }

    def test_roles_receive_isolated_environments(self):
        parent = {
            "PATH": "/bin",
            "DAIK_GH_TOKEN": "github-secret",
            "DAIK_TEST_TOKEN": "test-secret",
            "UNRELATED_SECRET": "must-not-leak",
        }
        config = self.config()
        worker_name, worker = select_process(config, "agent", "implementation")
        implementation = process_environment(worker_name, worker, parent)
        test_name, test = select_process(config, "agent", "testing")
        testing = process_environment(test_name, test, parent)

        self.assertEqual(implementation["GH_TOKEN"], "github-secret")
        self.assertEqual(implementation["LOG_LEVEL"], "info")
        self.assertNotIn("TEST_SERVER_TOKEN", implementation)
        self.assertEqual(testing["TEST_SERVER_TOKEN"], "test-secret")
        self.assertNotIn("GH_TOKEN", testing)
        self.assertNotIn("DAIK_GH_TOKEN", implementation)
        self.assertNotIn("UNRELATED_SECRET", testing)

    def test_required_error_names_variable_and_process_not_value(self):
        name, settings = select_process(self.config(), "agent", "testing")
        with self.assertRaisesRegex(
            ProcessConfigError,
            "processes.tests requires parent environment variable DAIK_TEST_TOKEN",
        ):
            process_environment(name, settings, {"DAIK_TEST_TOKEN": ""})

    def test_selection_does_not_depend_on_mapping_order(self):
        config = self.config()
        config["processes"] = dict(reversed(list(config["processes"].items())))
        name, _ = select_process(config, "agent", "review")
        self.assertEqual(name, "workers")

    def test_resolved_parent_values_are_redacted_recursively(self):
        _, settings = select_process(self.config(), "agent", "implementation")
        secrets = process_secrets(settings, {"DAIK_GH_TOKEN": "secret-marker"})

        self.assertEqual(redact("error: secret-marker", secrets), "error: [REDACTED]")
        self.assertEqual(
            redact_value({"result": ["secret-marker"]}, secrets),
            {"result": ["[REDACTED]"]},
        )


if __name__ == "__main__":
    unittest.main()
