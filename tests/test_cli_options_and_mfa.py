"""Regression coverage for configuration precedence and MFA selection."""

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from aws_assume_role import aws_assume_role as cli  # noqa: E402
from aws_assume_role.onelogin_client import Device, OneLoginClient, handle_saml_endpoint_response  # noqa: E402


class OptionsTest(unittest.TestCase):
    def test_cli_overrides_profile_and_profile_overrides_global(self):
        config = {
            "profile": "work",
            "app_id": "global-app",
            "aws_account_id": "global-account",
            "aws_role_name": "global-role",
            "aws_region": "global-region",
            "profiles": {
                "work": {
                    "app_id": "profile-app",
                    "aws_account_id": "profile-account",
                    "aws_role_name": "profile-role",
                }
            },
        }
        argv = ["cli", "--aws-account-id", "cli-account"]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(cli, "get_config", return_value=config):
            options = cli.get_options()

        self.assertEqual(options.aws_account_id, "cli-account")
        self.assertEqual(options.aws_role_name, "profile-role")
        self.assertEqual(options.app_id, "profile-app")
        self.assertEqual(options.aws_region, "global-region")

    def test_mfa_type_from_config_can_be_overridden_on_cli(self):
        for args, expected in [
            ([], "OneLogin SMS"),
            (["--mfa-device-type", "Google Authenticator"], "Google Authenticator"),
        ]:
            with self.subTest(args=args):
                with mock.patch.object(sys, "argv", ["cli"] + args):
                    with mock.patch.object(cli, "get_config", return_value={"mfa_device_type": "OneLogin SMS"}):
                        self.assertEqual(cli.get_options().mfa_device_type, expected)

    def test_keychain_options_remain_available(self):
        argv = ["cli", "--keychain-account", "work-account"]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(cli, "get_config", return_value={}):
            options = cli.get_options()
        self.assertEqual(options.keychain_account, "work-account")
        self.assertEqual(options.keychain_service, "onelogin")


class MfaSelectionTest(unittest.TestCase):
    def make_client(self, sms_data):
        client = mock.Mock(spec=OneLoginClient)
        client.error = None
        response = handle_saml_endpoint_response(
            {
                "message": "MFA is required",
                "state_token": "state-token",
                "user": {"id": 42},
                "devices": [{"device_id": 999, "device_type": "Google Authenticator"}],
            },
            2,
        )
        client.get_saml_assertion.return_value = response
        client.get_otp_devices.return_value = [
            Device({"id": 1, "type_display_name": "Google Authenticator", "user_display_name": "Personal phone"}),
            Device(sms_data),
        ]
        success = handle_saml_endpoint_response({"message": "Success", "data": "saml-assertion"}, 2)
        client.get_saml_assertion_verifying.side_effect = [response, success]
        return client

    def test_automatic_sms_selection_uses_factor_type_and_triggers_sms(self):
        for sms_data in [
            {
                "id": 2,
                "type_display_name": "Work SMS",
                "auth_factor_name": "OneLogin SMS",
                "user_display_name": "Work phone",
            },
            {"id": 2, "type_display_name": "OneLogin SMS"},
        ]:
            with self.subTest(sms_data=sms_data):
                client = self.make_client(sms_data)
                with redirect_stdout(io.StringIO()), mock.patch.object(cli, "get_selection") as select:
                    result = cli.get_saml_response(
                        client,
                        "user@example.com",
                        "password",
                        123,
                        "acme",
                        cmd_otp="123456",
                        mfa_device_type="OneLogin SMS",
                    )
                select.assert_not_called()
                client.get_otp_devices.assert_called_once_with(42)
                self.assertEqual(result["saml_response"], "saml-assertion")
                self.assertEqual(result["mfa_verify_info"], {"device_id": 2, "device_type": "OneLogin SMS"})
                self.assertEqual(
                    client.get_saml_assertion_verifying.call_args_list,
                    [
                        mock.call(123, 2, "state-token", None, do_not_notify=True),
                        mock.call(123, 2, "state-token", "123456", do_not_notify=True),
                    ],
                )

    def test_missing_mfa_type_falls_back_to_selection_with_enriched_labels(self):
        client = self.make_client(
            {
                "id": 2,
                "type_display_name": "Work SMS",
                "auth_factor_name": "OneLogin SMS",
                "user_display_name": "Work phone",
            }
        )
        output = io.StringIO()
        with redirect_stdout(output), mock.patch.object(cli, "get_selection", return_value=1) as select:
            result = cli.get_saml_response(
                client, "user@example.com", "password", 123, "acme", cmd_otp="123456", mfa_device_type="Missing factor"
            )
        select.assert_called_once_with(2)
        self.assertIn("OneLogin SMS (Work phone)", output.getvalue())
        self.assertEqual(result["saml_response"], "saml-assertion")


if __name__ == "__main__":
    unittest.main()
