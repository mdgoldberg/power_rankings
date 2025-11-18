import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Frame,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from power_rankings.league_config import resolve_league_id

DEFAULT_STATE_PATH = Path.home() / ".cache" / "power_rankings" / "espn_state.json"

logger = logging.getLogger(__name__)

SCHEDULE_TABLE_SELECTOR = "div.matchup--table table.Table"
EMAIL_SELECTOR = "[data-testid='InputIdentityFlowValue']"
PASSWORD_SELECTOR = "[data-testid='InputPassword']"
SUBMIT_SELECTOR = "[data-testid='BtnSubmit']"


class MissingCredentialsError(RuntimeError):
    """Raised when ESPN credentials are required but missing."""


class LoginAutomationError(RuntimeError):
    """Raised when the automated login flow cannot complete."""


@dataclass(slots=True)
class FetchConfig:
    league_id: int
    season: int
    output_dir: Path
    output_filename: str | None = None
    username: str | None = None
    password: str | None = None
    force_refresh: bool = False
    headless: bool = True
    state_path: Path = DEFAULT_STATE_PATH

    def resolve_credentials(self) -> tuple[str, str]:
        username = self.username or os.getenv("ESPN_USERNAME")
        password = self.password or os.getenv("ESPN_PASSWORD")
        if not username or not password:
            raise MissingCredentialsError(
                "ESPN credentials are required. Provide them as options or set "
                "the ESPN_USERNAME and ESPN_PASSWORD environment variables."
            )
        return username, password

    @property
    def schedule_url(self) -> str:
        return (
            "https://fantasy.espn.com/football/league/schedule"
            f"?leagueId={self.league_id}&seasonId={self.season}"
        )

    @property
    def output_path(self) -> Path:
        filename = self.output_filename or f"{self.season}.html"
        return self.output_dir / filename

    @property
    def launch_args(self) -> list[str]:
        if self.headless:
            return []
        return ["--start-minimized", "--window-position=0,0"]


def download_schedule_html(config: FetchConfig) -> Path:
    """
    Download the league schedule page as HTML.

    The HTML is saved to config.output_dir/<season>.html and the path is returned.
    """
    output_path = config.output_path
    if output_path.exists() and not config.force_refresh:
        return output_path

    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        launch_kwargs: dict[str, Any] = {"headless": config.headless}
        if config.launch_args:
            launch_kwargs["args"] = config.launch_args
            logger.info(
                "Launching Chromium in headed mode (window will start minimized). "
                "Bring it to the foreground if interaction is required."
            )
        browser = p.chromium.launch(**launch_kwargs)
        context = _create_browser_context(browser, config)

        try:
            html = _get_schedule_html(context, config)
        finally:
            context.close()
            browser.close()

    output_path.write_text(html, encoding="utf-8")
    return output_path


def ensure_schedule_file(
    html_filename: Path | None,
    *,
    auto_fetch: bool,
    league_id: int | None,
    league_name: str | None,
    leagues_file: Path | None,
    season: int | None,
    download_dir: Path | None,
    force_refresh: bool,
    headless: bool,
    username: str | None,
    password: str | None,
) -> Path:
    if html_filename is not None:
        if html_filename.exists():
            return html_filename
        if not auto_fetch:
            raise MissingCredentialsError(
                f"HTML file '{html_filename}' does not exist. Enable --auto-fetch to download it."
            )

    if not auto_fetch:
        raise MissingCredentialsError(
            "No HTML file supplied. Pass --auto-fetch with --league-id and --season to download it."
        )

    resolved_league_id = resolve_league_id(league_id, league_name, leagues_file)

    if resolved_league_id is None:
        raise MissingCredentialsError(
            "League information is required for auto-fetch. Specify --league-id or --league."
        )

    if season is None:
        raise MissingCredentialsError("--season is required when using --auto-fetch.")

    target_dir = download_dir
    if target_dir is None:
        if league_name:
            target_dir = Path("html") / league_name
        else:
            target_dir = Path("html") / f"league_{resolved_league_id}"
    output_filename = None

    if html_filename is not None:
        target_dir = html_filename.parent
        output_filename = html_filename.name

    config = FetchConfig(
        league_id=resolved_league_id,
        season=season,
        output_dir=target_dir,
        output_filename=output_filename,
        username=username,
        password=password,
        force_refresh=force_refresh,
        headless=headless,
    )
    return download_schedule_html(config)


def _get_schedule_html(context: BrowserContext, config: FetchConfig) -> str:
    page = context.new_page()
    try:
        page.goto(config.schedule_url, wait_until="domcontentloaded")
        logger.debug("Navigated to schedule page at %s", config.schedule_url)

        login_required = _requires_login(page)
        if login_required:
            if config.state_path.exists():
                logger.info(
                    "Stored ESPN login state missing or invalid; attempting fresh login for league %s season %s.",
                    config.league_id,
                    config.season,
                )
            username, password = config.resolve_credentials()
            logger.info("Login required for league %s season %s", config.league_id, config.season)
            _perform_login(page, username, password)
            try:
                page.wait_for_url("**/football/league/schedule**", timeout=60_000)
            except PlaywrightTimeoutError as exc:
                raise LoginAutomationError(
                    "Timed out waiting for the league schedule page after logging in."
                ) from exc

        logger.debug("Waiting for schedule table content to render.")
        try:
            page.wait_for_selector(
                SCHEDULE_TABLE_SELECTOR,
                state="visible",
                timeout=60_000,
            )
        except PlaywrightTimeoutError as exc:
            logger.error("Timed out waiting for the schedule table to render.", exc_info=True)
            raise LoginAutomationError(
                "Timed out waiting for the schedule table to render after loading the page."
            ) from exc
        logger.debug("Schedule table detected; capturing HTML.")
        html = page.content()
        _persist_storage_state(context, config.state_path)
        logger.debug("Schedule page content fetched successfully.")
        return html
    finally:
        page.close()


def _requires_login(page: Page) -> bool:
    """Detect whether the current page is showing the Disney login prompt."""
    login_indicators = ("login", "signin", "registerdisney")
    page_url = page.url.lower()
    if any(token in page_url for token in login_indicators):
        logger.debug("Login required because page URL contains an indicator: %s", page.url)
        return True

    overlay_open = _is_login_overlay_open(page)
    login_frame = page.frame(name="oneid-iframe")

    if login_frame is None:
        if not overlay_open:
            logger.debug("Login iframe not detected; assuming session is still valid.")
            return False
        logger.debug("Login overlay detected without iframe; waiting for iframe attachment.")
        try:
            login_frame = _get_login_frame(page, timeout_ms=10_000)
        except (LoginAutomationError, PlaywrightTimeoutError):
            logger.debug(
                "Login overlay reported but iframe unavailable within timeout; treating login as required."
            )
            return True

    logger.debug("Login iframe present; overlay_open=%s", overlay_open)

    if overlay_open:
        logger.debug("Login required because the ESPN overlay is active.")
        return True

    email_locator = login_frame.locator(EMAIL_SELECTOR)
    try:
        count = email_locator.count()
    except PlaywrightError:
        logger.debug(
            "Failed to evaluate login email locator; treating login as required.",
            exc_info=True,
        )
        return True

    if count == 0:
        logger.debug(
            "Login iframe present but email input selector missing; treating login as required."
        )
        return True

    try:
        email_visible = email_locator.first.is_visible()
    except PlaywrightError:
        logger.debug(
            "Error determining visibility of login email input; treating login as required.",
            exc_info=True,
        )
        return True

    if email_visible:
        logger.debug("Login required because the email input is visible inside the login iframe.")
        return True

    logger.debug("Login iframe present but email input hidden; assuming session is still valid.")
    logger.debug("Existing ESPN session is still valid; skipping login.")
    return False


def _is_login_overlay_open(page: Page) -> bool:
    try:
        return bool(
            page.evaluate(
                "Boolean(document && document.documentElement && "
                "document.documentElement.classList.contains('oneid-lightbox-open'))"
            )
        )
    except PlaywrightError:
        logger.debug(
            "Error checking for login overlay state; assuming overlay is closed.", exc_info=True
        )
        return False


def _get_login_frame(page: Page, timeout_ms: int = 30_000) -> Frame:
    try:
        logger.debug("Waiting for ESPN login iframe to attach (timeout=%sms).", timeout_ms)
        iframe_handle = page.wait_for_selector(
            "iframe#oneid-iframe, iframe[name='oneid-iframe']",
            state="attached",
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError as exc:
        raise LoginAutomationError(
            "Could not locate the ESPN login iframe during login automation."
        ) from exc

    assert iframe_handle is not None
    frame = iframe_handle.content_frame()
    if frame is None:
        raise LoginAutomationError("Login iframe was found, but no frame content is available.")
    logger.debug("Login iframe attached and frame handle acquired.")
    return frame


def _perform_login(page: Page, username: str, password: str) -> None:
    login_frame = _get_login_frame(page)
    logger.info("Starting ESPN login flow via iframe.")

    _fill_visible(login_frame, EMAIL_SELECTOR, username, "username/email field", timeout_ms=20_000)
    _click_visible(login_frame, SUBMIT_SELECTOR, "username submit button", timeout_ms=15_000)

    try:
        login_frame.wait_for_selector(PASSWORD_SELECTOR, state="visible", timeout=30_000)
    except PlaywrightTimeoutError as exc:
        logger.error("Password field did not appear after submitting username.", exc_info=True)
        raise LoginAutomationError(
            "Timed out waiting for the ESPN password field after submitting the username."
        ) from exc

    _fill_visible(login_frame, PASSWORD_SELECTOR, password, "password field", timeout_ms=15_000)
    _click_visible(login_frame, SUBMIT_SELECTOR, "final login button", timeout_ms=15_000)

    try:
        page.wait_for_function(
            "document && document.documentElement && !document.documentElement.classList.contains('oneid-lightbox-open')",
            timeout=30_000,
        )
    except PlaywrightTimeoutError:
        logger.warning(
            "Login overlay still active after timeout; continuing but downstream waits may fail."
        )


def _fill_visible(
    page_or_frame: Page | Frame,
    selector: str,
    value: str,
    description: str,
    timeout_ms: int,
) -> None:
    locator = page_or_frame.locator(selector)
    locator.wait_for(state="visible", timeout=timeout_ms)
    locator.fill(value)
    logger.debug("Filled %s using selector '%s'.", description, selector)


def _click_visible(
    page_or_frame: Page | Frame,
    selector: str,
    description: str,
    timeout_ms: int,
) -> None:
    locator = page_or_frame.locator(selector)
    locator.wait_for(state="visible", timeout=timeout_ms)
    locator.click()
    logger.debug("Clicked %s using selector '%s'.", description, selector)


def _create_browser_context(browser: Any, config: FetchConfig) -> BrowserContext:
    if config.state_path.exists():
        try:
            logger.debug("Loading Playwright storage state from %s", config.state_path)
            return browser.new_context(storage_state=str(config.state_path))
        except PlaywrightError as exc:
            logger.warning(
                "Failed to load cached ESPN login state from %s; creating fresh context. (%s)",
                config.state_path,
                exc,
            )
    return browser.new_context()


def _persist_storage_state(context: BrowserContext, state_path: Path) -> None:
    try:
        context.storage_state(path=str(state_path))
        logger.debug("Persisted Playwright storage state to %s", state_path)
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to persist Playwright storage state to %s; future sessions may require login.",
            state_path,
            exc_info=True,
        )
