import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from learning.models import AnswerAttempt
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture(autouse=True)
def static_for_live_server(settings):
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def browser(live_server, seeded, user):
    with sync_playwright() as runtime:
        options = {"headless": True, "chromium_sandbox": True}
        if os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH"):
            options["executable_path"] = os.environ["PLAYWRIGHT_EXECUTABLE_PATH"]
        browser = runtime.chromium.launch(**options)
        yield browser
        browser.close()


def answer_count():
    # Playwright owns an event loop on the test thread; Django ORM stays synchronous.
    from django.db import close_old_connections

    def count():
        try:
            return AnswerAttempt.objects.count()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(count).result()


def login(page, base):
    page.goto(base + "/login/")
    page.get_by_label("ユーザー名").fill("learner-one")
    page.get_by_label("パスワード").fill("Synthetic-check-7391")
    page.get_by_role("button", name="ログイン", exact=True).click()
    expect(page.get_by_role("heading", name="今日も、一問から。")).to_be_visible()


@pytest.mark.parametrize("width", [360, 390, 768, 1280])
def test_B01_B02_B04_B05_B06_mobile_flow(browser, live_server, seeded, user, width):
    context = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    login(page, live_server.url)
    page.get_by_text("科目 （未選択はすべて）", exact=True).click()
    page.get_by_label("無線工学", exact=True).check()
    page.get_by_role("button", name="条件を適用").click()
    expect(page.locator(".count strong")).to_have_text("3")
    page.get_by_role("button", name="学習をはじめる").click()
    expect(page.locator(".katex").first).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("body").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)") >= 16
    assert page.locator(".choice").first.bounding_box()["height"] >= 44
    zoom_button = page.locator(".figure").first
    zoom_button.focus()
    page.keyboard.press("Enter")
    expect(page.locator("dialog")).to_be_visible()
    page.locator("#zoom").focus()
    page.locator("#zoom").press("End")
    assert (
        page.locator("#large-image").bounding_box()["width"]
        > page.locator(".zoom-area").bounding_box()["width"]
    )
    page.keyboard.press("Escape")
    expect(zoom_button).to_be_focused()
    page.locator(".choice[value=second]").focus()
    assert (
        page.locator(".choice[value=second]").evaluate("e=>getComputedStyle(e).outlineStyle")
        != "none"
    )
    before = page.url
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    assert page.url == before
    assert page.locator("#result").get_attribute("aria-live") == "polite"
    expect(page.locator(".katex-display")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    Path(".local/screenshots").mkdir(parents=True, exist_ok=True)
    page.screenshot(path=f".local/screenshots/study-{width}.png", full_page=True)
    page.get_by_role("link", name="次の問題", exact=True).click()
    expect(page.get_by_role("heading", name="2 / 3 問目")).to_be_visible()
    page.get_by_role("link", name="成績", exact=True).click()
    expect(page.locator(".rate")).to_have_text("100.0%")
    assert not errors
    context.close()


def test_B03_response_lost_retry_and_reload(browser, live_server, seeded, user):
    context = browser.new_context(viewport={"width": 390, "height": 850})
    page = context.new_page()
    login(page, live_server.url)
    page.get_by_role("button", name="学習をはじめる").click()

    def lost_response(route):
        response = route.fetch()
        assert response.status == 200
        route.abort("failed")

    page.route("**/api/answer/**", lost_response, times=1)
    page.locator(".choice[value=second]").evaluate("button=>{button.click();button.click();}")
    expect(page.locator("#send-status")).to_contain_text("保存状況を確認できません")
    assert answer_count() == 1
    expect(page.locator(".choice").first).to_be_disabled()
    page.get_by_role("button", name="同じ回答を再送").click()
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    page.reload()
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    assert answer_count() == 1
    context.close()


def test_B02_no_javascript_post(browser, live_server, seeded, user):
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    login(page, live_server.url)
    page.get_by_role("button", name="学習をはじめる").click()
    page.locator(".choice[value=second]").click()
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    assert answer_count() == 1
    context.close()
