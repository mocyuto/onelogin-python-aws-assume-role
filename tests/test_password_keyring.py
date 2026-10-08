"""Regression coverage for saving and reusing OneLogin passwords."""

import io
import sys
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aws_assume_role import aws_assume_role as cli  # noqa: E402


class SavePasswordOptionsTest(unittest.TestCase):
    def test_save_password_from_config_and_command_line(self):
        for config, args, expected in [
            (None, [], False),
            ({"save_password": False}, [], False),
            ({"save_password": True}, [], True),
            ({"save_password": False}, ["--save-password"], True),
        ]:
            with self.subTest(config=config, args=args):
                with mock.patch.object(sys, "argv", ["cli"] + args):
                    with mock.patch.object(cli, "get_config", return_value=config):
                        self.assertEqual(cli.get_options().save_password, expected)

    def test_service_only_entry_follows_current_username(self):
        config = {"username": "alice@example.com", "keychain_service": "custom", "save_password": True}
        with mock.patch.object(sys, "argv", ["cli"]), mock.patch.object(cli, "get_config", return_value=config):
            options = cli.get_options()
        with mock.patch.object(cli.keyring, "get_password") as read:
            cli.get_password_from_keyring("bob@example.com", options.keychain_service, options.keychain_account)
        with redirect_stdout(io.StringIO()), mock.patch.object(cli.keyring, "set_password") as save:
            cli.save_password_to_keyring(
                "bob@example.com", "bob-password", options.keychain_service, options.keychain_account
            )
        read.assert_called_once_with("custom", "bob")
        save.assert_called_once_with("custom", "bob", "bob-password")


class AuthenticationCompleted(Exception):
    """Stop the mocked CLI before AWS role selection and credential output."""


class PasswordKeyringTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.output = self.stack.enter_context(redirect_stdout(io.StringIO()))
        self.config = {
            "username": "user@example.com",
            "app_id": "123",
            "subdomain": "acme",
            "save_password": True,
        }
        self.result = {
            "username_or_email": "user@example.com",
            "password": "verified-password",
            "onelogin_subdomain": "acme",
            "mfa_verify_info": None,
            "saml_response": "c2FtbA==",
        }
        self.stack.enter_context(mock.patch.object(sys, "argv", ["cli"]))
        self.stack.enter_context(mock.patch.object(cli, "get_config", return_value=self.config))
        self.stack.enter_context(mock.patch.object(cli, "get_client"))
        self.read = self.stack.enter_context(mock.patch.object(cli.keyring, "get_password", return_value=None))
        self.save = self.stack.enter_context(mock.patch.object(cli.keyring, "set_password"))
        self.prompt = self.stack.enter_context(
            mock.patch.object(cli.getpass, "getpass", return_value="entered-password")
        )
        self.authenticate = self.stack.enter_context(
            mock.patch.object(cli, "get_saml_response", return_value=self.result)
        )
        self.stack.enter_context(mock.patch.object(cli, "get_attributes", side_effect=AuthenticationCompleted))

    def run_authentication(self):
        with self.assertRaises(AuthenticationCompleted):
            cli.main()

    def test_saves_verified_password_after_authentication(self):
        self.run_authentication()
        self.read.assert_called_once_with("onelogin-aws-assume-role", "user@example.com")
        self.assertEqual(self.authenticate.call_args.args[2], "entered-password")
        self.save.assert_called_once_with("onelogin-aws-assume-role", "user@example.com", "verified-password")
        self.assertIn("Password saved to OS keychain", self.output.getvalue())

    def test_reuses_saved_password_without_save_flag(self):
        self.config["save_password"] = False
        self.read.return_value = "saved-password"
        self.run_authentication()
        self.assertEqual(self.authenticate.call_args.args[2], "saved-password")
        self.prompt.assert_not_called()
        self.save.assert_not_called()

    def test_explicit_keychain_settings_use_same_entry_for_reading_and_saving(self):
        for settings, expected in [
            ({"keychain_service": "custom", "keychain_account": "work"}, ("custom", "work")),
            ({"keychain_account": "work"}, ("onelogin", "work")),
            ({"keychain_service": "custom"}, ("custom", "user")),
        ]:
            with self.subTest(settings=settings):
                self.config.pop("keychain_service", None)
                self.config.pop("keychain_account", None)
                self.config.update(settings)
                self.read.reset_mock()
                self.save.reset_mock()
                self.run_authentication()
                self.read.assert_called_once_with(*expected)
                self.save.assert_called_once_with(*expected, "verified-password")

    def test_keychain_service_supports_interactive_username(self):
        del self.config["username"]
        self.config["keychain_service"] = "custom"
        with mock.patch.object(sys, "stdin", io.StringIO("user@example.com\n")):
            self.run_authentication()
        self.read.assert_called_once_with("custom", "user")
        self.save.assert_called_once_with("custom", "user", "verified-password")

    def test_command_line_password_takes_precedence_over_keyring(self):
        with mock.patch.object(sys, "argv", ["cli", "--onelogin-password", "cli-password"]):
            self.run_authentication()
        self.assertEqual(self.authenticate.call_args.args[2], "cli-password")
        self.read.assert_not_called()
        self.prompt.assert_not_called()

    def test_failed_authentication_does_not_save_password(self):
        self.authenticate.side_effect = RuntimeError("Authentication failed")
        with self.assertRaisesRegex(RuntimeError, "Authentication failed"):
            cli.main()
        self.save.assert_not_called()

    def test_incomplete_mfa_does_not_save_password(self):
        for assertion in [None, ""]:
            with self.subTest(assertion=assertion):
                self.result["saml_response"] = assertion
                self.run_authentication()
                self.save.assert_not_called()

    def test_cached_saml_does_not_save_or_request_password(self):
        cached = dict(self.result, app_id="123")
        cached.pop("password")
        with mock.patch.object(sys, "argv", ["cli", "--cache-saml"]):
            with mock.patch.object(cli, "get_data_from_cache", return_value=cached):
                with mock.patch.object(cli, "is_valid_saml_assertion", return_value=True):
                    self.run_authentication()
        self.authenticate.assert_not_called()
        self.read.assert_not_called()
        self.prompt.assert_not_called()
        self.save.assert_not_called()

    def test_unavailable_keyring_falls_back_to_password_prompt(self):
        self.read.side_effect = cli.keyring.errors.NoKeyringError("No backend")
        self.run_authentication()
        self.prompt.assert_called_once()
        self.assertEqual(self.authenticate.call_args.args[2], "entered-password")
        self.assertIn("Warning: Failed to retrieve password", self.output.getvalue())

    def test_password_storage_failure_does_not_abort_authenticated_session(self):
        self.save.side_effect = cli.keyring.errors.PasswordSetError("Storage unavailable")
        self.run_authentication()
        self.assertIn("Warning: Failed to save password", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
