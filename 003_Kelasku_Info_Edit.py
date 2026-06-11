import asyncio
import base64
import os
import tempfile
from datetime import datetime
from dataclasses import dataclass, field
from settings import EmailConfig, LoginConfig
from pathlib import Path
from typing import Literal

import matplotlib.pyplot as plt
from fpdf import FPDF
from mailjet_rest import Client
from playwright.async_api import TimeoutError, async_playwright

Status = Literal["PASSED", "FAILED"]


@dataclass(frozen=True)
class TestConfig(LoginConfig):
    info_text: str = os.getenv("KELASKU_EDIT_INFO_TEXT", f"Test Edit {datetime.now().strftime('%Y%m%d%H%M%S')}")
    timeout_ms: int = int(os.getenv("TIMEOUT_MS", "10000"))
    wait_after_action_seconds: int = int(os.getenv("WAIT_AFTER_ACTION_SECONDS", "3"))
    screenshot_path: Path = Path(os.getenv("SCREENSHOT_PATH", "screenshot3_kelasku_info_edit.png"))
    report_path: Path = Path(os.getenv("REPORT_PATH", "test_report_kelasku_info_edit.pdf"))


@dataclass
class TestLog:
    message: str
    status: Status = "PASSED"


@dataclass
class TestResult:
    logs: list[TestLog] = field(default_factory=list)
    passed: bool = True

    def add_log(self, message: str, status: Status = "PASSED") -> None:
        self.logs.append(TestLog(message=message, status=status))
        if status == "FAILED":
            self.passed = False
        print(f"{status}: {message}")


class PdfReport:
    def generate(self, result: TestResult, screenshot_path: Path, output_path: Path) -> None:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        self._add_title(pdf)
        self._add_donut_chart(pdf, result.logs)
        self._add_logs_table(pdf, result.logs)
        self._add_evidence(pdf, screenshot_path)

        pdf.output(str(output_path))
        print(f"PDF report generated: {output_path}")

    @staticmethod
    def _add_title(pdf: FPDF) -> None:
        pdf.set_font("Arial", style="B", size=16)
        pdf.cell(200, 10, txt="Kelasku Info Edit Test Report", ln=True, align="C")
        pdf.ln(10)

    @staticmethod
    def _add_donut_chart(pdf: FPDF, logs: list[TestLog]) -> None:
        passed_count = sum(1 for log in logs if log.status == "PASSED")
        failed_count = sum(1 for log in logs if log.status == "FAILED")
        total_count = len(logs)
        success_rate = (passed_count / total_count * 100) if total_count else 0

        plt.figure(figsize=(4, 4))
        plt.pie(
            [passed_count, failed_count],
            labels=["Passed", "Failed"],
            autopct="%1.1f%%",
            colors=["#4CAF50", "#FF5252"],
            startangle=140,
            wedgeprops={"width": 0.35, "edgecolor": "white"},
        )
        plt.text(0, 0, f"{success_rate:.1f}%\nSuccess", ha="center", va="center", fontsize=12, weight="bold")
        plt.title("Test Result Summary")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as chart_file:
            chart_path = Path(chart_file.name)

        try:
            plt.savefig(chart_path, bbox_inches="tight")
            pdf.image(str(chart_path), x=60, y=45, w=90)
            pdf.ln(105)
        finally:
            plt.close()
            chart_path.unlink(missing_ok=True)

    @staticmethod
    def _add_logs_table(pdf: FPDF, logs: list[TestLog]) -> None:
        pdf.set_font("Arial", style="B", size=12)
        pdf.cell(0, 10, txt="Detailed Test Logs:", ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", size=10)
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(120, 10, txt="Log Message", border=1, align="C", fill=True)
        pdf.cell(40, 10, txt="Status", border=1, align="C", fill=True)
        pdf.ln()

        for log in logs:
            pdf.cell(120, 10, txt=log.message, border=1)
            pdf.cell(40, 10, txt=log.status, border=1, align="C")
            pdf.ln()

    @staticmethod
    def _add_evidence(pdf: FPDF, screenshot_path: Path) -> None:
        pdf.add_page()
        pdf.set_font("Arial", style="B", size=14)
        pdf.cell(0, 10, txt="Evidence Testing:", ln=True, align="L")
        pdf.ln(10)

        if screenshot_path.exists():
            pdf.image(str(screenshot_path), x=20, y=30, w=170)
        else:
            pdf.cell(0, 10, txt="No evidence available.", ln=True)


class EmailSender:
    def __init__(self, config: EmailConfig):
        self.config = config

    def send_attachment(self, attachment_path: Path) -> None:
        if not self.config.enabled:
            print("Email sending skipped. Set SEND_EMAIL=true to enable.")
            return

        if not self.config.api_key or not self.config.api_secret:
            raise ValueError("MAILJET_API_KEY and MAILJET_API_SECRET are required when SEND_EMAIL=true.")

        encoded_file = self._read_attachment(attachment_path)
        mailjet = Client(auth=(self.config.api_key, self.config.api_secret), version="v3.1")
        result = mailjet.send.create(data=self._build_payload(attachment_path.name, encoded_file))
        print(f"Email sent status: {result.status_code}")

    @staticmethod
    def _read_attachment(attachment_path: Path) -> str:
        with attachment_path.open("rb") as file:
            return base64.b64encode(file.read()).decode("utf-8")

    def _build_payload(self, filename: str, encoded_file: str) -> dict:
        return {
            "Messages": [
                {
                    "From": {"Email": self.config.sender_email, "Name": self.config.sender_name},
                    "To": [{"Email": self.config.recipient_email, "Name": self.config.recipient_name}],
                    "Subject": self.config.subject,
                    "TextPart": self.config.body,
                    "Attachments": [
                        {
                            "ContentType": "application/pdf",
                            "Filename": filename,
                            "Base64Content": encoded_file,
                        }
                    ],
                }
            ]
        }


async def run_kelasku_info_edit_test(config: TestConfig) -> TestResult:
    result = TestResult()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=config.headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await login(page, config, result)
            await edit_kelasku_info(page, config, result)
            await asyncio.sleep(config.wait_after_action_seconds)
            await take_screenshot(page, config.screenshot_path)
        finally:
            await context.close()
            await browser.close()

    return result


async def login(page, config: TestConfig, result: TestResult) -> None:
    try:
        await page.goto(config.login_url, timeout=config.timeout_ms)
        result.add_log("Successfully navigated to the login page.")

        await page.get_by_text("Masukan ID Pengguna").click(timeout=config.timeout_ms)
        result.add_log("Clicked on 'Masukan ID Pengguna'.")

        await page.get_by_placeholder("ID Pengguna / Email").fill(config.username, timeout=config.timeout_ms)
        result.add_log("Filled 'ID Pengguna / Email'.")

        await page.get_by_placeholder("Kata Sandi").fill(config.password, timeout=config.timeout_ms)
        result.add_log("Filled 'Kata Sandi'.")

        await page.get_by_role("button", name="Masuk").click(timeout=config.timeout_ms)
        result.add_log("Clicked on 'Masuk' button.")

        alert = page.get_by_role("alert").locator("div").filter(has_text="Berhasil Masuk")
        await alert.wait_for(timeout=config.timeout_ms)
        result.add_log("Login successful: 'Berhasil Masuk' alert found.")
    except TimeoutError:
        result.add_log("Login step timed out.", "FAILED")
        raise


async def wait_for_spinner_to_disappear(page, config: TestConfig, result: TestResult) -> None:
    try:
        await page.locator(".container-spinner").wait_for(state="hidden", timeout=config.timeout_ms)
        result.add_log("Waited for loading spinner to disappear.")
    except TimeoutError:
        result.add_log("Loading spinner still visible or unstable after timeout.", "FAILED")
        raise


async def edit_kelasku_info(page, config: TestConfig, result: TestResult) -> None:
    try:
        await wait_for_spinner_to_disappear(page, config, result)
        await page.get_by_role("menuitem", name="Kelasku").click(timeout=config.timeout_ms)
        result.add_log("Clicked on 'Kelasku' menu item.")
        await asyncio.sleep(3)
        result.add_log("Waited for Kelasku page UI to finish loading.")

        await dump_kelasku_buttons(page, result)
        await open_edit_info_form(page, config, result)
        await fill_rich_text_area(page, config, result)

        await page.get_by_role("button", name="Ubah Info").click(timeout=config.timeout_ms)
        result.add_log("Clicked on 'Ubah Info' button.")
    except TimeoutError:
        result.add_log("Failed to complete Kelasku info edit steps.", "FAILED")
        raise


async def dump_kelasku_buttons(page, result: TestResult) -> None:
    buttons = await page.locator("button").evaluate_all(
        """
        buttons => buttons.map((button, index) => ({
            index,
            text: button.innerText,
            ariaLabel: button.getAttribute('aria-label'),
            title: button.getAttribute('title'),
            className: button.className,
            html: button.outerHTML.slice(0, 500),
        }))
        """
    )

    print("DEBUG: Buttons found before edit click:")
    for button in buttons:
        print(button)

    result.add_log(f"Dumped {len(buttons)} buttons before edit click for selector debugging.")


async def open_edit_info_form(page, config: TestConfig, result: TestResult) -> None:
    edit_selectors = [
        (
            "edit SVG data-src",
            page.locator('svg[data-src="/static/media/edit-3-o.3e0954cb.svg"]').first,
        ),
        (
            "button containing edit SVG data-src",
            page.locator('button:has(svg[data-src="/static/media/edit-3-o.3e0954cb.svg"])').first,
        ),
        (
            "Kelasku info pencil CSS",
            page.locator(
                "#root > div > section > section > main > div > div:nth-child(2) > div > div:nth-child(1) > div:nth-child(3) > div > div:nth-child(1) > span > span:nth-child(2) > button:nth-child(1) > span > div > div > svg"
            ),
        ),
        ("button role 'edit'", page.get_by_role("button", name="edit")),
        ("button role 'pencil'", page.get_by_role("button", name="pencil")),
        ("button role 'form'", page.get_by_role("button", name="form")),
        ("Ant Design edit icon", page.locator("button:has(.anticon-edit)").first),
        ("Ant Design form icon", page.locator("button:has(.anticon-form)").first),
        ("SVG edit icon", page.locator("button:has(svg[data-icon='edit'])").first),
        ("SVG form icon", page.locator("button:has(svg[data-icon='form'])").first),
    ]

    try:
        await click_first_available(edit_selectors, config.timeout_ms)
        result.add_log("Clicked on edit/pencil button.")
    except TimeoutError:
        result.add_log("Edit button not found. Opening class detail first.")
        await open_class_detail(page, config, result)
        await dump_kelasku_buttons(page, result)
        await click_first_available(edit_selectors, config.timeout_ms)
        result.add_log("Clicked on edit/pencil button after opening class detail.")

    await asyncio.sleep(2)
    result.add_log("Waited for edit form to open.")
    await dump_edit_fields(page, result)


async def open_class_detail(page, config: TestConfig, result: TestResult) -> None:
    detail_selectors = [
        ("open icon image", page.locator('button:has(img[alt="open-icon"])').first),
        ("open icon img", page.locator('img[alt="open-icon"]').first),
        ("first non-disabled right button", page.locator("button:not([disabled]):has(.bi-chevron-right)").first),
        ("pagination right", page.locator("button:not([disabled]):has(svg[data-icon='right'])").first),
    ]

    await click_first_available(detail_selectors, config.timeout_ms)
    result.add_log("Clicked on class detail/open button.")
    await asyncio.sleep(3)
    result.add_log("Waited for class detail page to load.")


async def dump_edit_fields(page, result: TestResult) -> None:
    fields = await page.evaluate(
        """
        () => ({
            iframes: [...document.querySelectorAll('iframe')].map((el, index) => ({
                index,
                title: el.getAttribute('title'),
                src: el.getAttribute('src'),
                html: el.outerHTML.slice(0, 300),
            })),
            inputs: [...document.querySelectorAll('input')].map((el, index) => ({
                index,
                type: el.getAttribute('type'),
                placeholder: el.getAttribute('placeholder'),
                value: el.value,
                className: el.className,
                html: el.outerHTML.slice(0, 300),
            })),
            textareas: [...document.querySelectorAll('textarea')].map((el, index) => ({
                index,
                placeholder: el.getAttribute('placeholder'),
                value: el.value,
                className: el.className,
                html: el.outerHTML.slice(0, 300),
            })),
            contenteditable: [...document.querySelectorAll('[contenteditable="true"]')].map((el, index) => ({
                index,
                text: el.innerText,
                className: el.className,
                html: el.outerHTML.slice(0, 300),
            })),
            buttons: [...document.querySelectorAll('button')].map((el, index) => ({
                index,
                text: el.innerText,
                ariaLabel: el.getAttribute('aria-label'),
                className: el.className,
                html: el.outerHTML.slice(0, 300),
            })),
        })
        """
    )

    print("DEBUG: Edit form fields found:")
    print(fields)
    result.add_log("Dumped edit form fields for selector debugging.")


async def fill_rich_text_area(page, config: TestConfig, result: TestResult) -> None:
    iframe_titles = await page.locator("iframe").evaluate_all(
        "iframes => iframes.map((iframe, index) => ({ index, title: iframe.getAttribute('title'), src: iframe.getAttribute('src') }))"
    )
    print(f"DEBUG: Iframes found: {iframe_titles}")

    frame_selectors = [
        ('iframe[title="Rich Text Area"]', page.frame_locator('iframe[title="Rich Text Area"]')),
        ('iframe[title*="Rich Text"]', page.frame_locator('iframe[title*="Rich Text"]')),
        ("first iframe", page.frame_locator("iframe").first),
    ]

    last_error = None
    for selector_name, frame in frame_selectors:
        try:
            await frame.locator("html").click(timeout=config.timeout_ms)
            await frame.locator("body").fill(config.info_text, timeout=config.timeout_ms)
            result.add_log(f"Filled '{config.info_text}' into Rich Text Area using {selector_name}.")
            return
        except TimeoutError as error:
            last_error = error

    raise last_error or TimeoutError("Rich Text Area iframe not found.")


async def click_first_available(named_locators, timeout_ms: int) -> None:
    last_error = None

    for _, locator in named_locators:
        try:
            await locator.click(timeout=timeout_ms)
            return
        except TimeoutError as error:
            last_error = error

    raise last_error or TimeoutError("No matching locator found.")


async def take_screenshot(page, screenshot_path: Path) -> None:
    await page.screenshot(path=str(screenshot_path))
    print(f"Screenshot saved to {screenshot_path}")


async def main() -> None:
    test_config = TestConfig()
    email_config = EmailConfig()

    try:
        result = await run_kelasku_info_edit_test(test_config)
    except TimeoutError as error:
        print(f"Test stopped because required step timed out: {error}")
        result = TestResult(passed=False)
        result.add_log("Test stopped because required step timed out.", "FAILED")

    PdfReport().generate(result, test_config.screenshot_path, test_config.report_path)
    EmailSender(email_config).send_attachment(test_config.report_path)


if __name__ == "__main__":
    asyncio.run(main())
