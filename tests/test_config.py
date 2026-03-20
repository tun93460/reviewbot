"""Tests for reviewbot/config.py."""
import pytest

from reviewbot.config import AppConfig


def test_validate_missing_token(monkeypatch):
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)
    config = AppConfig(gitlab_token="")
    errors = config.validate()
    assert errors == ["GITLAB_TOKEN is not set"]


def test_validate_with_token(monkeypatch):
    config = AppConfig(gitlab_token="mytoken")
    assert config.validate() == []


def test_default_gitlab_url(monkeypatch):
    monkeypatch.delenv("GITLAB_URL", raising=False)
    config = AppConfig()
    assert config.gitlab_url == "https://gitlab.com"


def test_gitlab_username_strips_inline_comment(monkeypatch):
    # AppConfig strips everything after '#' so users can annotate .env values
    monkeypatch.setenv("GITLAB_USERNAME", "alice  # primary account")
    config = AppConfig()
    assert config.gitlab_username == "alice"
