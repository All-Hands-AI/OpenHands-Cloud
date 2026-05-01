"""Tests for create_slack_app.py — written before implementation (TDD RED phase)."""

import os
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from create_slack_app import (
    build_app_manifest,
    create_slack_app,
    main,
    missing_token_message,
    parse_args,
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def make_mock_response(response_data: dict, ok: bool = True) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = response_data
    if ok:
        mock.raise_for_status.return_value = None
    else:
        mock.raise_for_status.side_effect = Exception("HTTP error")
    return mock


def make_successful_create_response(
    app_id: str = "A0B12DUAWTX",
    client_id: str = "1234567890.9876543210",
    client_secret: str = "client_secret_value",
    signing_secret: str = "signing_secret_value",
    verification_token: str = "verification_token_value",
) -> dict:
    return {
        "ok": True,
        "app_id": app_id,
        "credentials": {
            "client_id": client_id,
            "client_secret": client_secret,
            "verification_token": verification_token,
            "signing_secret": signing_secret,
        },
        "oauth_authorize_url": "https://slack.com/oauth/v2/authorize?client_id=1234",
    }


@contextmanager
def mock_main_dependencies(response_data: dict | None = None):
    if response_data is None:
        response_data = make_successful_create_response()
    mocks = {}
    with patch("create_slack_app.requests.post") as mock_post:
        mock_post.return_value = make_mock_response(response_data)
        mocks["requests_post"] = mock_post
        yield mocks


# ---------------------------------------------------------------------------
# TestBuildAppManifest
# ---------------------------------------------------------------------------


class TestBuildAppManifest:
    def test_redirect_url_uses_base_domain(self):
        manifest = build_app_manifest("example.com")
        redirect_urls = manifest["oauth_config"]["redirect_urls"]
        assert "https://app.example.com/slack/install-callback" in redirect_urls
        assert redirect_urls[0].startswith("https://")

    def test_event_subscription_request_url_uses_base_domain(self):
        manifest = build_app_manifest("example.com")
        request_url = manifest["settings"]["event_subscriptions"]["request_url"]
        assert request_url == "https://app.example.com/slack/on-event"
        assert request_url.startswith("https://")

    def test_interactivity_request_url_uses_base_domain(self):
        manifest = build_app_manifest("example.com")
        request_url = manifest["settings"]["interactivity"]["request_url"]
        assert request_url == "https://app.example.com/slack/on-form-interaction"
        assert request_url.startswith("https://")

    def test_options_load_url_uses_base_domain(self):
        manifest = build_app_manifest("example.com")
        request_url = manifest["settings"]["interactivity"]["message_menu_options_url"]
        assert request_url == "https://app.example.com/slack/on-options-load"
        assert request_url.startswith("https://")

    def test_bot_event_is_app_mention(self):
        manifest = build_app_manifest("example.com")
        assert "app_mention" in manifest["settings"]["event_subscriptions"]["bot_events"]

    @pytest.mark.parametrize(
        "scope",
        [
            "app_mentions:read",
            "chat:write",
            "users:read",
            "channels:history",
            "groups:history",
            "mpim:history",
            "im:history",
        ],
    )
    def test_bot_scopes_include_required_scope(self, scope):
        manifest = build_app_manifest("example.com")
        assert scope in manifest["oauth_config"]["scopes"]["bot"]

    def test_no_user_scopes_configured(self):
        manifest = build_app_manifest("example.com")
        assert "user" not in manifest["oauth_config"]["scopes"]

    def test_display_name_defaults_to_openhands(self):
        manifest = build_app_manifest("example.com")
        assert manifest["features"]["bot_user"]["display_name"] == "OpenHands"
        assert manifest["display_information"]["name"] == "OpenHands"

    def test_bot_user_does_not_include_username_field(self):
        manifest = build_app_manifest("example.com")
        assert "username" not in manifest["features"]["bot_user"]

    def test_custom_app_name_sets_display_name(self):
        manifest = build_app_manifest("example.com", app_name="my-bot")
        assert manifest["features"]["bot_user"]["display_name"] == "my-bot"
        assert manifest["display_information"]["name"] == "my-bot"

    def test_interactivity_is_enabled(self):
        manifest = build_app_manifest("example.com")
        assert manifest["settings"]["interactivity"]["is_enabled"] is True

    def test_socket_mode_is_disabled(self):
        manifest = build_app_manifest("example.com")
        assert manifest["settings"]["socket_mode_enabled"] is False

    def test_always_online_is_false(self):
        manifest = build_app_manifest("example.com")
        assert manifest["features"]["bot_user"]["always_online"] is False

    def test_org_deploy_enabled_is_false(self):
        manifest = build_app_manifest("example.com")
        assert manifest["settings"]["org_deploy_enabled"] is False

    def test_token_rotation_enabled_is_false(self):
        manifest = build_app_manifest("example.com")
        assert manifest["settings"]["token_rotation_enabled"] is False


# ---------------------------------------------------------------------------
# TestCreateSlackApp
# ---------------------------------------------------------------------------


class TestCreateSlackApp:
    def test_calls_correct_api_endpoint(self):
        manifest = build_app_manifest("example.com")
        with patch("create_slack_app.requests.post") as mock_post:
            mock_post.return_value = make_mock_response(make_successful_create_response())
            create_slack_app(manifest, token="xoxe-test-token")
        assert mock_post.call_args[0][0] == "https://slack.com/api/apps.manifest.create"

    def test_includes_token_in_authorization_header(self):
        manifest = build_app_manifest("example.com")
        with patch("create_slack_app.requests.post") as mock_post:
            mock_post.return_value = make_mock_response(make_successful_create_response())
            create_slack_app(manifest, token="xoxe-my-token")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer xoxe-my-token"

    def test_sends_manifest_in_request_body(self):
        manifest = build_app_manifest("example.com")
        with patch("create_slack_app.requests.post") as mock_post:
            mock_post.return_value = make_mock_response(make_successful_create_response())
            create_slack_app(manifest, token="xoxe-test-token")
        assert mock_post.call_args[1]["json"]["manifest"] == manifest

    def test_returns_full_response_data(self):
        manifest = build_app_manifest("example.com")
        expected = make_successful_create_response()
        with patch("create_slack_app.requests.post") as mock_post:
            mock_post.return_value = make_mock_response(expected)
            result = create_slack_app(manifest, token="xoxe-test-token")
        assert result == expected

    def test_raises_on_slack_api_error(self):
        manifest = build_app_manifest("example.com")
        with patch("create_slack_app.requests.post") as mock_post:
            mock_post.return_value = make_mock_response({"ok": False, "error": "invalid_manifest"})
            with pytest.raises(RuntimeError, match="invalid_manifest"):
                create_slack_app(manifest, token="xoxe-test-token")

    def test_raises_on_http_error(self):
        manifest = build_app_manifest("example.com")
        with patch("create_slack_app.requests.post") as mock_post:
            mock_post.return_value = make_mock_response({}, ok=False)
            with pytest.raises(Exception):
                create_slack_app(manifest, token="xoxe-test-token")


# ---------------------------------------------------------------------------
# TestTokenResolution
# ---------------------------------------------------------------------------


class TestTokenResolution:
    def test_slack_token_read_from_env_when_not_passed(self):
        with patch.dict(os.environ, {"SLACK_CONFIG_TOKEN": "xoxe-from-env"}):
            args = parse_args(argv=["--base-domain", "example.com"])
        assert args.slack_token == "xoxe-from-env"

    def test_cli_token_takes_precedence_over_env(self):
        with patch.dict(os.environ, {"SLACK_CONFIG_TOKEN": "xoxe-from-env"}):
            args = parse_args(argv=["--base-domain", "example.com", "--slack-token", "xoxe-cli"])
        assert args.slack_token == "xoxe-cli"


# ---------------------------------------------------------------------------
# TestMissingTokenMessage
# ---------------------------------------------------------------------------


class TestMissingTokenMessage:
    def test_includes_api_slack_com_apps_url(self):
        assert "https://api.slack.com/apps" in missing_token_message()

    def test_instructs_to_click_generate_token(self):
        assert "Generate Token" in missing_token_message()

    def test_references_app_configuration_tokens_section(self):
        assert "Your App Configuration Tokens" in missing_token_message()

    def test_instructs_to_use_access_token(self):
        assert "access token" in missing_token_message()


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_prints_domain(self, capsys):
        with mock_main_dependencies():
            main(base_domain="example.com", slack_token="tok", dry_run=True)
        assert "example.com" in capsys.readouterr().out

    def test_dry_run_does_not_call_slack_api(self):
        with mock_main_dependencies() as mocks:
            main(base_domain="example.com", slack_token="tok", dry_run=True)
        mocks["requests_post"].assert_not_called()


# ---------------------------------------------------------------------------
# TestMain — output order and content
# ---------------------------------------------------------------------------


class TestMain:
    def test_outputs_client_id(self, capsys):
        with mock_main_dependencies(make_successful_create_response(client_id="cid-123")):
            main(base_domain="example.com", slack_token="tok")
        assert "cid-123" in capsys.readouterr().out

    def test_outputs_client_secret(self, capsys):
        with mock_main_dependencies(make_successful_create_response(client_secret="csec-456")):
            main(base_domain="example.com", slack_token="tok")
        assert "csec-456" in capsys.readouterr().out

    def test_outputs_signing_secret(self, capsys):
        with mock_main_dependencies(make_successful_create_response(signing_secret="ssec-789")):
            main(base_domain="example.com", slack_token="tok")
        assert "ssec-789" in capsys.readouterr().out

    def test_output_order_is_client_id_then_client_secret_then_signing_secret(self, capsys):
        with mock_main_dependencies(
            make_successful_create_response(
                client_id="CID", client_secret="CSEC", signing_secret="SSEC"
            )
        ):
            main(base_domain="example.com", slack_token="tok")
        out = capsys.readouterr().out
        cid_pos = out.index("CID")
        csec_pos = out.index("CSEC")
        ssec_pos = out.index("SSEC")
        assert cid_pos < csec_pos < ssec_pos

    def test_output_labels_client_id(self, capsys):
        with mock_main_dependencies():
            main(base_domain="example.com", slack_token="tok")
        assert "Slack Client ID" in capsys.readouterr().out

    def test_output_labels_client_secret(self, capsys):
        with mock_main_dependencies():
            main(base_domain="example.com", slack_token="tok")
        assert "Slack Client Secret" in capsys.readouterr().out

    def test_output_labels_signing_secret(self, capsys):
        with mock_main_dependencies():
            main(base_domain="example.com", slack_token="tok")
        assert "Slack Signing Secret" in capsys.readouterr().out

    def test_passes_token_to_api(self):
        with mock_main_dependencies() as mocks:
            main(base_domain="example.com", slack_token="xoxe-my-token")
        headers = mocks["requests_post"].call_args[1]["headers"]
        assert "xoxe-my-token" in headers["Authorization"]

    def test_passes_base_domain_to_manifest(self):
        with mock_main_dependencies() as mocks:
            main(base_domain="mycompany.com", slack_token="tok")
        redirect_urls = mocks["requests_post"].call_args[1]["json"]["manifest"]["oauth_config"][
            "redirect_urls"
        ]
        assert any("mycompany.com" in url for url in redirect_urls)

    def test_uses_custom_app_name(self):
        with mock_main_dependencies() as mocks:
            main(base_domain="example.com", slack_token="tok", app_name="custom-bot")
        manifest = mocks["requests_post"].call_args[1]["json"]["manifest"]
        assert manifest["display_information"]["name"] == "custom-bot"

    def test_display_name_is_OpenHands_when_no_app_name_provided(self):
        with mock_main_dependencies() as mocks:
            main(base_domain="example.com", slack_token="tok")
        manifest = mocks["requests_post"].call_args[1]["json"]["manifest"]
        assert manifest["display_information"]["name"] == "OpenHands"

    def test_bot_display_name_is_OpenHands_when_no_app_name_provided(self):
        with mock_main_dependencies() as mocks:
            main(base_domain="example.com", slack_token="tok")
        manifest = mocks["requests_post"].call_args[1]["json"]["manifest"]
        assert manifest["features"]["bot_user"]["display_name"] == "OpenHands"
