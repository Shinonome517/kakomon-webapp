import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from learning.models import AnswerAttempt
from learning.services import start_session
from playwright.sync_api import expect, sync_playwright
from questions.importer import import_bundle
from questions.models import Question

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
        browser_name = os.environ.get("PLAYWRIGHT_BROWSER", "chromium")
        options = {"headless": True}
        if browser_name == "chromium":
            options["chromium_sandbox"] = True
            if os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH"):
                options["executable_path"] = os.environ["PLAYWRIGHT_EXECUTABLE_PATH"]
        browser = getattr(runtime, browser_name).launch(**options)
        yield browser
        browser.close()


@pytest.fixture
def numbered_item(seeded, user):
    import_bundle(Path(__file__).parents[1] / "fixtures/synthetic-choice-numbers")
    return start_session(user, {"subjects": ["動作確認"]}, count=1).items.first()


@pytest.fixture
def long_session(seeded, user):
    question = Question.objects.get(stable_id="synthetic-01")
    revision = question.current_revision
    revision.explanation_blocks = [
        {"type": "markdown", "text": "\n\n".join(["長い解説の表示を確認する合成文章です。"] * 45)}
    ]
    revision.save(update_fields=["explanation_blocks"])
    return start_session(user, {}, count=2).items.first().pk


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


def login(page, base, password="Synthetic-check-7391"):
    page.goto(base + "/login/")
    page.get_by_label("ユーザー名").fill("learner-one")
    page.locator('[name="password"]').fill(password)
    page.get_by_role("button", name="ログイン", exact=True).click()
    expect(page.get_by_role("heading", name="今日も一問から始めましょう。")).to_be_visible()


def screenshot(page, name):
    Path(".local/screenshots").mkdir(parents=True, exist_ok=True)
    page.screenshot(path=f".local/screenshots/{name}.png", full_page=True)


@pytest.mark.parametrize("width", [360, 390, 768, 1280])
def test_B01_B02_B04_B05_B06_mobile_flow(browser, live_server, width):
    context = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    login(page, live_server.url)
    assert page.locator('input[type="checkbox"]:not(:checked)').count() == 0
    expect(page.get_by_role("button", name="条件を適用")).to_be_hidden()
    page.locator("#study-settings summary").filter(has_text="科目").click()
    page.get_by_label("法規", exact=True).focus()
    page.get_by_label("法規", exact=True).press("Space")
    expect(page.locator(".count strong")).to_have_text("3")
    expect(page.get_by_label("法規", exact=True)).to_be_focused()
    page.get_by_role("button", name="学習を始める").click()
    expect(page.locator(".katex").first).to_be_visible()
    expect(page.get_by_role("link", name="前の問題", exact=True)).to_have_count(0)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert page.locator("body").evaluate("e=>parseFloat(getComputedStyle(e).fontSize)") >= 16
    assert page.locator(".choice").first.bounding_box()["height"] >= 44
    assert page.get_by_role("button", name="わからない", exact=True).bounding_box()["height"] >= 44
    expect(page.locator(".choice-zoom")).to_have_count(1)
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
    # Native focus restoration can precede the app's queued close handler.
    page.evaluate("""() => {
        window.imageDialogClosed = new Promise(resolve => {
            document.querySelector('dialog').addEventListener('close', () => resolve(null), {once: true});
        });
    }""")
    page.keyboard.press("Escape")
    page.evaluate("() => window.imageDialogClosed")
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
    expect(page.locator("#send-status")).to_be_empty()
    expect(page.locator(".katex-display")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    primary = page.get_by_role("link", name="次の問題", exact=True).bounding_box()
    container = page.locator("#result .next").bounding_box()
    first_offset = primary["y"] - container["y"]
    screenshot(page, f"study-{width}")
    page.get_by_role("link", name="次の問題", exact=True).click()
    expect(page.get_by_role("heading", name="2 / 3 問目")).to_be_visible()
    page.locator(".choice").first.click()
    expect(page.get_by_role("link", name="次の問題", exact=True)).to_be_visible()
    previous = page.get_by_role("link", name="前の問題", exact=True).bounding_box()
    primary = page.get_by_role("link", name="次の問題", exact=True).bounding_box()
    container = page.locator("#result .next").bounding_box()
    assert abs(previous["y"] - primary["y"]) <= 2
    assert abs(primary["y"] - container["y"] - first_offset) <= 2
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.get_by_role("link", name="学習の記録", exact=True).click()
    expect(page.locator(".rate")).to_have_text("50.0%")
    assert not errors
    context.close()


@pytest.mark.parametrize("unknown", [False, True])
def test_B03_response_lost_retry_reload_and_previous(browser, live_server, unknown):
    context = browser.new_context(viewport={"width": 390, "height": 850})
    page = context.new_page()
    login(page, live_server.url)
    page.get_by_role("button", name="学習を始める").click()
    first_url = page.url
    pending_states = []

    def lost_response(route):
        pending_states.append(
            page.evaluate("""() => ({
            text: document.querySelector('#send-status').textContent,
            error: document.querySelector('#send-status').classList.contains('error'),
            disabled: [...document.querySelectorAll('#answer-form .choice, #answer-form [name="unknown"]')].every(b => b.disabled)
        })""")
        )
        response = route.fetch()
        assert response.status == 200
        route.abort("failed")

    page.route("**/api/answer/**", lost_response, times=1)
    button = page.locator('[name="unknown"]' if unknown else '.choice[value="second"]')
    button.evaluate("button=>{button.click();button.click();}")
    expect(page.locator("#send-status")).to_contain_text("保存状況を確認できません")
    assert pending_states == [{"text": "送信中…", "error": False, "disabled": True}]
    assert answer_count() == 1
    expect(page.locator(".choice").first).to_be_disabled()
    expect(page.locator('[name="unknown"]')).to_be_disabled()
    page.get_by_role("button", name="同じ回答を再送").click()
    result_name = "× 不正解" if unknown else "○ 正解"
    expect(page.get_by_role("heading", name=result_name, exact=True)).to_be_visible()
    expect(page.locator("#send-status")).to_be_empty()
    if unknown:
        expect(page.locator("#result")).to_contain_text("わからない（不正解として記録）")
    page.reload()
    expect(page.get_by_role("heading", name=result_name, exact=True)).to_be_visible()
    page.get_by_role("link", name="次の問題", exact=True).click()
    expect(page.locator("#previous-unanswered")).to_be_visible()
    page.get_by_role("link", name="前の問題", exact=True).click()
    assert page.url == first_url
    expect(page.get_by_role("heading", name=result_name, exact=True)).to_be_visible()
    expect(page.locator(".choice").first).to_be_disabled()
    expect(page.locator('[name="unknown"]')).to_be_disabled()
    assert answer_count() == 1
    context.close()


@pytest.mark.parametrize("unknown", [False, True])
def test_B02_no_javascript_filters_and_answer(browser, live_server, unknown):
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    login(page, live_server.url)
    expect(page.locator(".password-toggle")).to_have_count(0)
    page.locator("#study-settings summary").filter(has_text="科目").click()
    page.get_by_label("法規", exact=True).uncheck()
    page.get_by_role("button", name="条件を適用").click()
    expect(page.locator(".count strong")).to_have_text("3")
    page.get_by_role("button", name="学習を始める").click()
    page.locator('[name="unknown"]' if unknown else '.choice[value="second"]').click()
    expect(
        page.get_by_role("heading", name="× 不正解" if unknown else "○ 正解", exact=True)
    ).to_be_visible()
    assert answer_count() == 1
    page.get_by_role("link", name="学習の記録", exact=True).click()
    expect(page.get_by_role("button", name="条件を適用")).to_be_visible()
    page.locator("#stats-settings summary").filter(has_text="科目").click()
    page.get_by_label("法規", exact=True).uncheck()
    page.get_by_label("無線工学", exact=True).uncheck()
    page.get_by_role("button", name="条件を適用").click()
    expect(page.get_by_role("heading", name="学習の記録", exact=True)).to_be_visible()
    expect(page.locator("#id_subjects_error")).to_contain_text("科目を1つ以上選んでください。")
    expect(page.locator(".rate")).to_have_count(0)
    context.close()


@pytest.mark.parametrize("width", [360, 390])
def test_long_result_scroll_completion_and_button_order(long_session, browser, live_server, width):
    first_url = live_server.url + f"/study/{long_session}/"
    context = browser.new_context(viewport={"width": width, "height": 700})
    page = context.new_page()
    login(page, live_server.url)
    page.goto(first_url)
    page.locator(".choice[value=second]").click()
    result = page.locator("#result")
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    expect(result).to_be_focused()
    assert 0 <= result.bounding_box()["y"] <= 40
    assert page.get_by_role("heading", name="○ 正解", exact=True).bounding_box()["y"] < 200
    assert result.bounding_box()["height"] > 1000
    page.get_by_role("link", name="次の問題", exact=True).click()
    page.locator('[name="unknown"]').click()
    expect(page.locator(".completion")).to_have_text("このセットは完了です。")
    assert page.locator(".completion").evaluate("e => e.closest('[role=status]') !== null")
    links = page.locator("#result .settings-link, #result .next a")
    expect(links).to_have_text(["出題設定へ", "前の問題", "学習の記録を見る"])
    assert page.locator(".completion").bounding_box()["y"] < links.first.bounding_box()["y"]
    # macOS WebKit uses Option-Tab to include links in native keyboard navigation.
    tab_key = (
        "Alt+Tab" if browser.browser_type.name == "webkit" and sys.platform == "darwin" else "Tab"
    )
    links.first.focus()
    page.keyboard.press(tab_key)
    expect(links.nth(1)).to_be_focused()
    page.keyboard.press(tab_key)
    expect(links.nth(2)).to_be_focused()
    assert abs(links.nth(1).bounding_box()["y"] - links.nth(2).bounding_box()["y"]) <= 2
    assert all(link.bounding_box()["height"] >= 44 for link in links.all())
    primary = links.nth(2).bounding_box()
    container = page.locator("#result .next").bounding_box()
    assert abs(primary["x"] + primary["width"] - container["x"] - container["width"]) <= 2
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    screenshot(page, f"final-result-{width}")
    links.nth(1).click()
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    assert page.url == first_url
    assert answer_count() == 2
    context.close()


@pytest.mark.parametrize("width", [360, 390])
def test_number_only_choices_keep_accessible_text(numbered_item, browser, live_server, width):
    context = browser.new_context(viewport={"width": width, "height": 850})
    page = context.new_page()
    login(page, live_server.url)
    page.goto(live_server.url + f"/study/{numbered_item.pk}/")
    choices = page.locator(".choice")
    expect(choices).to_have_count(2)
    expect(choices.first).to_have_accessible_name(re.compile(r"1.*Aは2、Bは3"))
    expect(choices.nth(1)).to_have_accessible_name(re.compile(r"2.*合成の組合せ表"))
    expect(page.locator(".choice-label")).to_have_text(["1", "2"])
    expect(page.locator(".choice-zoom")).to_have_count(0)
    expect(page.locator(".figure")).to_have_count(1)
    for choice in choices.all():
        assert 44 <= choice.bounding_box()["height"] < 90
        assert choice.locator(".sr-only").bounding_box()["width"] == 1
        assert (
            choice.locator(".sr-only").evaluate("e=>getComputedStyle(e).clipPath") == "inset(50%)"
        )
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    screenshot(page, f"numbered-choice-{width}")
    choices.first.focus()
    page.keyboard.press("Enter")
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    context.close()


def test_auto_filters_validation_failure_recovery_and_stats(browser, live_server):
    context = browser.new_context(viewport={"width": 390, "height": 850})
    page = context.new_page()
    login(page, live_server.url)
    page.locator("#study-settings summary").filter(has_text="科目").click()
    page.get_by_label("法規", exact=True).uncheck()
    expect(page.locator(".count strong")).to_have_text("3")
    page.get_by_label("無線工学", exact=True).uncheck()
    expect(page.locator("#id_subjects_error")).to_contain_text("科目を1つ以上選んでください。")
    expect(page.get_by_role("button", name="学習を始める")).to_be_disabled()
    expect(page.locator(".count")).to_have_count(0)
    page.route("**/api/filters/home/**", lambda route: route.abort("failed"), times=1)
    page.get_by_label("無線工学", exact=True).check()
    expect(page.locator("[data-preview-status]")).to_contain_text("条件を反映できませんでした")
    expect(page.locator("#id_subjects_error")).to_be_empty()
    assert page.locator('#id_subjects [aria-invalid="true"]').count() == 0
    expect(page.locator("#filter-preview")).to_be_hidden()
    expect(page.get_by_role("button", name="学習を始める")).to_be_disabled()
    page.get_by_role("button", name="条件を適用").click()
    expect(page.locator(".count strong")).to_have_text("3")
    page.get_by_role("button", name="学習を始める").click()
    page.locator(".choice[value=second]").click()
    expect(page.get_by_role("heading", name="○ 正解", exact=True)).to_be_visible()
    page.get_by_role("link", name="学習の記録", exact=True).click()
    expect(page.locator(".rate")).to_have_text("100.0%")
    expect(page.locator("#filter-preview")).to_contain_text("学習進捗 1 / 対象 6 問")
    groups = page.locator("details[data-topic-subject]")
    expect(groups).to_have_count(2)
    assert groups.evaluate_all("nodes => nodes.every(n => !n.open)")
    engineering = page.locator('details[data-topic-subject="無線工学"]')
    engineering.locator("summary").click()
    expect(engineering.locator("[data-topic-code]")).to_contain_text("動作確認・計算")
    page.locator("#stats-settings summary").filter(has_text="科目").click()
    page.get_by_label("法規", exact=True).focus()
    page.get_by_label("法規", exact=True).press("Space")
    expect(page.locator("#filter-preview")).to_contain_text("学習進捗 1 / 対象 3 問")
    assert engineering.get_attribute("open") is not None
    expect(page.get_by_label("法規", exact=True)).to_be_focused()
    expect(page.locator("#id_ordering, #id_count")).to_have_count(0)
    page.locator("#id_target").select_option("unanswered")
    expect(page.locator(".rate")).to_have_text("—（未回答）")
    expect(page.locator("#filter-preview")).to_contain_text("学習進捗 0 / 対象 2 問")
    screenshot(page, "stats-390")
    context.close()


def test_late_filter_response_does_not_replace_newer_result(browser, live_server):
    context = browser.new_context()
    page = context.new_page()
    login(page, live_server.url)
    # Emulate a response already in flight that cannot be cancelled by AbortController.
    page.evaluate("""() => {
        window.previewRequests = [];
        window.fetch = () => new Promise(resolve => window.previewRequests.push(resolve));
        window.resolvePreview = (index, count) => window.previewRequests[index]({
            ok: true, status: 200,
            json: async () => ({valid: true, errors: {}, count, html: `<p class="count">対象 <strong>${count}</strong> 問</p>`})
        });
    }""")
    page.locator("#id_target").select_option("incorrect")
    expect(page.get_by_role("button", name="学習を始める")).to_be_disabled()
    page.locator("#id_target").select_option("all")
    page.evaluate("() => window.resolvePreview(1, 6)")
    expect(page.locator(".count strong")).to_have_text("6")
    page.evaluate("() => window.resolvePreview(0, 0)")
    expect(page.locator(".count strong")).to_have_text("6")
    expect(page.get_by_role("button", name="学習を始める")).to_be_enabled()
    context.close()


@pytest.mark.parametrize("width", [360, 390])
def test_clear_topics_and_reselect(browser, live_server, width):
    context = browser.new_context(viewport={"width": width, "height": 850})
    page = context.new_page()
    login(page, live_server.url)
    page.locator("#study-settings summary").filter(has_text="分野").click()
    clear = page.get_by_role("button", name="すべて外す", exact=True)
    assert clear.bounding_box()["height"] >= 44
    clear.focus()
    clear.press("Enter")
    expect(page.locator("#id_topics_error")).to_contain_text("分野を1つ以上選んでください。")
    expect(clear).to_be_focused()
    assert page.locator('[name="topics"]:checked').count() == 0
    assert (
        page.locator('[name="subjects"]:not(:checked), [name="papers"]:not(:checked)').count() == 0
    )
    expect(page.get_by_role("button", name="学習を始める")).to_be_disabled()
    expect(page.locator(".count")).to_have_count(0)
    page.locator('[name="topics"]').first.check()
    expect(page.locator("#id_topics_error")).to_be_empty()
    expect(page.locator(".count strong")).to_have_text("3")
    expect(page.get_by_role("button", name="学習を始める")).to_be_enabled()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    screenshot(page, f"clear-topics-{width}")
    context.close()


@pytest.mark.parametrize("javascript", [True, False])
def test_password_visibility_and_change_submission(browser, live_server, javascript):
    context = browser.new_context(
        java_script_enabled=javascript, viewport={"width": 360, "height": 850}
    )
    page = context.new_page()
    page.goto(live_server.url + "/login/")
    password = page.locator('[name="password"]')
    expect(password).to_have_attribute("type", "password")
    if javascript:
        toggle = page.locator(".password-toggle")
        expect(toggle).to_have_attribute("aria-pressed", "false")
        toggle.focus()
        page.keyboard.press("Enter")
        expect(password).to_have_attribute("type", "text")
        expect(toggle).to_have_attribute("aria-pressed", "true")
        page.keyboard.press("Enter")
        expect(password).to_have_attribute("type", "password")
        assert toggle.bounding_box()["height"] >= 44
    else:
        expect(page.locator(".password-toggle")).to_have_count(0)
    page.get_by_label("ユーザー名").fill("learner-one")
    password.fill("Synthetic-check-7391")
    if javascript:
        page.locator(".password-toggle").click()
        expect(password).to_have_attribute("type", "text")
    page.get_by_role("button", name="ログイン", exact=True).click()
    expect(page.get_by_role("heading", name="今日も一問から始めましょう。")).to_be_visible()
    page.goto(live_server.url + "/password/")
    names = ["old_password", "new_password1", "new_password2"]
    for name in names:
        field = page.locator(f'[name="{name}"]')
        expect(field).to_have_attribute("type", "password")
        field.fill("Synthetic-check-7391" if name == "old_password" else "Synthetic-changed-8642")
        if javascript:
            toggle = page.locator(f'button[aria-controls="id_{name}"]')
            expect(toggle).to_have_attribute("aria-pressed", "false")
            toggle.click()
            expect(field).to_have_attribute("type", "text")
            for other in names:
                if other != name:
                    expect(page.locator(f'[name="{other}"]')).to_have_attribute("type", "password")
            toggle.click()
            expect(field).to_have_attribute("type", "password")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if javascript:
        screenshot(page, "password-360")
    page.get_by_role("button", name="変更して学習へ").click()
    expect(page.get_by_role("heading", name="今日も一問から始めましょう。")).to_be_visible()
    page.get_by_role("button", name="ログアウト", exact=True).click()
    login(page, live_server.url, password="Synthetic-changed-8642")
    context.close()
