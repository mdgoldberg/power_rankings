from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from power_rankings.web_fetch import (
    FetchConfig,
    LoginAutomationError,
    PlaywrightTimeoutError,
    _get_login_frame,
    _get_schedule_html,
    _perform_login,
    _requires_login,
    EMAIL_SELECTOR,
    PASSWORD_SELECTOR,
    SCHEDULE_TABLE_SELECTOR,
    SUBMIT_SELECTOR,
)


def _make_page(html: str = "<html></html>") -> MagicMock:
    page = MagicMock()
    page.goto = MagicMock()
    page.wait_for_url = MagicMock()
    page.wait_for_load_state = MagicMock()
    page.wait_for_selector = MagicMock()
    page.content.return_value = html
    page.close = MagicMock()
    page.url = "https://fantasy.espn.com/login"
    page.frames = []
    page.frame = MagicMock(return_value=None)
    locator = MagicMock()
    locator.count.return_value = 0
    first = MagicMock()
    first.is_visible.return_value = False
    locator.first = first
    page.locator.return_value = locator
    page.evaluate.return_value = False
    page.wait_for_selector = MagicMock()
    return page


def _make_context(page: MagicMock) -> MagicMock:
    context = MagicMock()
    context.new_page.return_value = page
    context.storage_state = MagicMock()
    return context


def _make_config(tmp_path: Path) -> FetchConfig:
    return FetchConfig(
        league_id=123,
        season=2025,
        output_dir=tmp_path,
        username="user@example.com",
        password="secret",
        state_path=tmp_path / "espn_state.json",
    )


def test_get_schedule_html_logs_in_when_required(tmp_path: Path):
    page = _make_page("<html>after login</html>")
    context = _make_context(page)
    config = _make_config(tmp_path)

    with (
        patch("power_rankings.web_fetch._requires_login", return_value=True) as requires_login,
        patch("power_rankings.web_fetch._perform_login") as perform_login,
    ):
        html = _get_schedule_html(context, config)

    context.new_page.assert_called_once_with()
    page.goto.assert_called_once_with(config.schedule_url, wait_until="domcontentloaded")
    requires_login.assert_called_once_with(page)
    perform_login.assert_called_once_with(page, config.username, config.password)
    page.wait_for_url.assert_called_once_with("**/football/league/schedule**", timeout=60_000)
    page.wait_for_load_state.assert_not_called()
    page.wait_for_selector.assert_called_once_with(
        SCHEDULE_TABLE_SELECTOR,
        state="visible",
        timeout=60_000,
    )
    page.content.assert_called_once_with()
    page.close.assert_called_once_with()
    context.storage_state.assert_called_once_with(path=str(config.state_path))
    assert html == "<html>after login</html>"


def test_get_schedule_html_skips_login_when_not_required(tmp_path: Path):
    page = _make_page("<html>no login needed</html>")
    context = _make_context(page)
    config = _make_config(tmp_path)

    with (
        patch("power_rankings.web_fetch._requires_login", return_value=False) as requires_login,
        patch("power_rankings.web_fetch._perform_login") as perform_login,
    ):
        html = _get_schedule_html(context, config)

    context.new_page.assert_called_once_with()
    page.goto.assert_called_once_with(config.schedule_url, wait_until="domcontentloaded")
    requires_login.assert_called_once_with(page)
    perform_login.assert_not_called()
    page.wait_for_url.assert_not_called()
    page.wait_for_load_state.assert_not_called()
    page.wait_for_selector.assert_called_once_with(
        SCHEDULE_TABLE_SELECTOR,
        state="visible",
        timeout=60_000,
    )
    page.content.assert_called_once_with()
    page.close.assert_called_once_with()
    context.storage_state.assert_called_once_with(path=str(config.state_path))
    assert html == "<html>no login needed</html>"


def test_get_schedule_html_raises_when_login_times_out(tmp_path: Path):
    page = _make_page()
    context = _make_context(page)
    config = _make_config(tmp_path)
    page.wait_for_url.side_effect = PlaywrightTimeoutError("timeout")

    with (
        patch("power_rankings.web_fetch._requires_login", return_value=True),
        patch("power_rankings.web_fetch._perform_login"),
        pytest.raises(LoginAutomationError),
    ):
        _get_schedule_html(context, config)

    page.wait_for_url.assert_called_once_with("**/football/league/schedule**", timeout=60_000)
    page.wait_for_load_state.assert_not_called()
    page.content.assert_not_called()
    page.wait_for_selector.assert_not_called()
    context.storage_state.assert_not_called()


def _make_base_page() -> MagicMock:
    page = MagicMock()
    page.url = "https://fantasy.espn.com/football/league/schedule"
    page.frames = []
    page.frame = MagicMock(return_value=None)
    locator = MagicMock()
    locator.count.return_value = 0
    first = MagicMock()
    first.is_visible.return_value = False
    locator.first = first
    page.locator.return_value = locator
    page.evaluate.return_value = False
    return page


def test_requires_login_detects_login_url():
    page = _make_base_page()
    page.url = "https://registerdisney.go.com/login"

    assert _requires_login(page) is True


def test_requires_login_detects_email_field():
    page = _make_base_page()
    frame = MagicMock()
    email_locator = MagicMock()
    email_locator.count.return_value = 1
    email_locator.first.is_visible.return_value = True
    frame.locator.return_value = email_locator
    page.frame.return_value = frame

    assert _requires_login(page) is True
    email_locator.count.assert_called_once_with()
    email_locator.first.is_visible.assert_called_once_with()


def test_requires_login_false_when_email_hidden():
    page = _make_base_page()
    frame = MagicMock()
    email_locator = MagicMock()
    email_locator.count.return_value = 1
    email_locator.first.is_visible.return_value = False
    frame.locator.return_value = email_locator
    page.frame.return_value = frame

    assert _requires_login(page) is False
    email_locator.count.assert_called_once_with()
    email_locator.first.is_visible.assert_called_once_with()


def test_requires_login_true_when_overlay_open(monkeypatch):
    page = _make_base_page()
    page.evaluate.return_value = True
    page.frame.return_value = None

    frame = MagicMock()
    email_locator = MagicMock()
    email_locator.count.return_value = 1
    email_locator.first.is_visible.return_value = False
    frame.locator.return_value = email_locator

    get_login_frame = MagicMock(return_value=frame)
    monkeypatch.setattr("power_rankings.web_fetch._get_login_frame", get_login_frame)

    assert _requires_login(page) is True
    get_login_frame.assert_called_once()


def test_requires_login_true_when_email_selector_missing():
    page = _make_base_page()
    frame = MagicMock()
    email_locator = MagicMock()
    email_locator.count.return_value = 0
    frame.locator.return_value = email_locator
    page.frame.return_value = frame

    assert _requires_login(page) is True


def test_requires_login_true_when_overlay_open_iframe_timeout(monkeypatch):
    page = _make_base_page()
    page.evaluate.return_value = True
    page.frame.return_value = None

    def raise_timeout(*_args, **_kwargs):
        raise PlaywrightTimeoutError("timeout")

    monkeypatch.setattr("power_rankings.web_fetch._get_login_frame", raise_timeout)

    assert _requires_login(page) is True


def test_requires_login_false_when_no_indicators(monkeypatch):
    page = _make_base_page()

    def raise_login_error(*_args, **_kwargs):
        raise LoginAutomationError("no iframe")

    monkeypatch.setattr("power_rankings.web_fetch._get_login_frame", raise_login_error)
    assert _requires_login(page) is False


def test_get_login_frame_wraps_timeout():
    page = MagicMock()
    page.wait_for_selector.side_effect = PlaywrightTimeoutError("timeout")

    with pytest.raises(LoginAutomationError):
        _get_login_frame(page)


def test_perform_login_handles_two_step_flow(monkeypatch):
    page = MagicMock()
    page.wait_for_function = MagicMock()

    frame = MagicMock()
    frame.wait_for_selector = MagicMock()
    email_locator = MagicMock()
    password_locator = MagicMock()
    submit_first = MagicMock()
    submit_second = MagicMock()

    locator_sequence = {
        EMAIL_SELECTOR: [email_locator],
        SUBMIT_SELECTOR: [submit_first, submit_second],
        PASSWORD_SELECTOR: [password_locator],
    }

    def locator_side_effect(selector: str):
        options = locator_sequence.get(selector)
        if not options:
            raise AssertionError(f"Unexpected selector requested: {selector}")
        locator = options.pop(0)
        locator.wait_for = MagicMock()
        locator.fill = getattr(locator, "fill", MagicMock())
        locator.click = getattr(locator, "click", MagicMock())
        return locator

    frame.locator.side_effect = locator_side_effect

    monkeypatch.setattr(
        "power_rankings.web_fetch._get_login_frame", lambda *_args, **_kwargs: frame
    )

    _perform_login(page, "user@example.com", "s3cret")

    email_locator.wait_for.assert_called_once_with(state="visible", timeout=20_000)
    email_locator.fill.assert_called_once_with("user@example.com")
    submit_first.wait_for.assert_called_once_with(state="visible", timeout=15_000)
    submit_first.click.assert_called_once_with()
    frame.wait_for_selector.assert_called_once_with(
        PASSWORD_SELECTOR, state="visible", timeout=30_000
    )
    password_locator.wait_for.assert_called_once_with(state="visible", timeout=15_000)
    password_locator.fill.assert_called_once_with("s3cret")
    submit_second.wait_for.assert_called_once_with(state="visible", timeout=15_000)
    submit_second.click.assert_called_once_with()
    page.wait_for_function.assert_called_once_with(
        "document && document.documentElement && !document.documentElement.classList.contains('oneid-lightbox-open')",
        timeout=30_000,
    )
