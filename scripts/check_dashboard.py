"""Browser regression check. Requires the app, Playwright, and a Chromium browser."""
import argparse

from playwright.sync_api import expect, sync_playwright


def login(page, base_url, email, password):
    page.goto(base_url + "/login")
    page.get_by_label("Email address").fill(email)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()


def logout(page, base_url):
    page.get_by_role("button", name="User menu", exact=True).click()
    page.get_by_role("button", name="Sign out", exact=True).click()
    expect(page).to_have_url(base_url + "/login")


def check_account(page, base_url, email, password, names, first_total, shared_total):
    login(page, base_url, email, password)
    total = page.get_by_test_id("revenue-total")
    expect(total).to_have_text(first_total, timeout=20000)
    actual_names = page.get_by_label("Select Property").locator("option").all_text_contents()
    assert actual_names == names, actual_names

    page.get_by_label("Select Property").select_option("prop-001")
    expect(total).to_have_text(shared_total)
    page.get_by_label("Month", exact=True).fill("2024-02")
    expect(total).to_have_text("USD 0.00")
    page.get_by_label("Report period").select_option("annual")
    expect(total).to_have_text(shared_total)
    page.get_by_label("Report period").select_option("all")
    expect(total).to_have_text(shared_total)

    page.reload()
    expect(total).to_have_text(first_total)
    logout(page, base_url)
    print(email + ": properties, reporting periods, reload, and logout PASS")


def check_stale_response(page, base_url):
    login(page, base_url, "sunset@propertyflow.com", "client_a_2024")
    total = page.get_by_test_id("revenue-total")
    expect(total).to_have_text("USD 2,250.00", timeout=20000)
    page.get_by_label("Select Property").select_option("prop-002")
    expect(total).to_have_text("USD 4,975.50")

    # Hold one old response while the user selects another property.
    pending = []
    page.route("**/api/v1/dashboard/summary?property_id=prop-003&**", lambda route: pending.append(route))
    page.get_by_label("Select Property").select_option("prop-003")
    page.wait_for_function("document.querySelector('[role=status]') !== null")
    # Drive the browser event loop until the held request is registered.
    for _ in range(100):
        if pending:
            break
        page.wait_for_timeout(20)
    assert pending, "Expected a held request for prop-003"
    held = pending.pop()
    page.get_by_label("Select Property").select_option("prop-001")
    expect(total).to_have_text("USD 2,250.00")
    held.continue_()
    page.unroute("**/api/v1/dashboard/summary?property_id=prop-003&**")
    page.wait_for_load_state("networkidle")
    expect(total).to_have_text("USD 2,250.00")
    logout(page, base_url)
    print("Late response cannot replace the selected property's total: PASS")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:3000")
    parser.add_argument("--channel", default=None, help="Use msedge for installed Microsoft Edge")
    args = parser.parse_args()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=args.channel, headless=True)
        page = browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            check_account(
                page, args.base_url, "sunset@propertyflow.com", "client_a_2024",
                ["Beach House Alpha", "City Apartment Downtown", "Country Villa Estate"],
                "USD 2,250.00", "USD 2,250.00",
            )
            check_account(
                page, args.base_url, "ocean@propertyflow.com", "client_b_2024",
                ["Lakeside Cottage", "Mountain Lodge Beta", "Urban Loft Modern"],
                "USD 1,776.50", "USD 0.00",
            )
            check_stale_response(page, args.base_url)
            assert not errors, errors
            print("No uncaught JavaScript errors: PASS")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
