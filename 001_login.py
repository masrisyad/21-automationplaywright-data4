import asyncio
import base64
import os
import tempfile
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
class LoginTestConfig(LoginConfig):
    screenshot_path: Path = Path("screenshot1.png")
    report_path: Path = Path("test_report.pdf")
    wait_after_login_seconds: int = int(os.getenv("WAIT_AFTER_LOGIN_SECONDS", "3"))


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
        pdf.cell(200, 10, txt="Test Report", ln=True, align="C")
        pdf.ln(10)

    @staticmethod
    def _add_donut_chart(pdf: FPDF, logs: list[TestLog]) -> None:
        passed_count = sum(1 for log in logs if log.status == "PASSED")
        failed_count = sum(1 for log in logs if log.status == "FAILED")
        total_count = len(logs)
        success_rate = (passed_count / total_count * 100) if total_count else 0

        values = [passed_count, failed_count]
        labels = ["Passed", "Failed"]
        colors = ["#4CAF50", "#FF5252"]

        plt.figure(figsize=(4, 4))
        plt.pie(
            values,
            labels=labels,
            autopct="%1.1f%%",
            colors=colors,
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
                    "From": {
                        "Email": self.config.sender_email,
                        "Name": self.config.sender_name,
                    },
                    "To": [
                        {
                            "Email": self.config.recipient_email,
                            "Name": self.config.recipient_name,
                        }
                    ],
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


async def run_login_test(config: LoginConfig) -> TestResult:
    result = TestResult()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=config.headless)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await open_login_page(page, config, result)
            await submit_login_form(page, config, result)
            await verify_success_alert(page, config, result)
            await asyncio.sleep(config.wait_after_login_seconds)
            await take_screenshot(page, config.screenshot_path)
        finally:
            await context.close()
            await browser.close()

    return result


async def open_login_page(page, config: LoginConfig, result: TestResult) -> None:
    try:
        await page.goto(config.login_url, timeout=config.timeout_ms)
        result.add_log("Successfully navigated to the login page.")
    except TimeoutError:
        result.add_log(f"Timeout: Failed to load login page within {config.timeout_ms} ms.", "FAILED")
        raise


async def submit_login_form(page, config: LoginConfig, result: TestResult) -> None:
    try:
        await page.get_by_text("Masukan ID Pengguna").click(timeout=config.timeout_ms)
        result.add_log("Clicked on 'Masukan ID Pengguna'.")

        await page.get_by_placeholder("ID Pengguna / Email").fill(config.username, timeout=config.timeout_ms)
        result.add_log("Filled 'ID Pengguna / Email'.")

        await page.get_by_placeholder("Kata Sandi").fill(config.password, timeout=config.timeout_ms)
        result.add_log("Filled 'Kata Sandi'.")

        await page.get_by_role("button", name="Masuk").click(timeout=config.timeout_ms)
        result.add_log("Clicked on 'Masuk' button.")
    except TimeoutError:
        result.add_log("Timeout: Interaction with the login form took too long.", "FAILED")
        raise


async def verify_success_alert(page, config: LoginConfig, result: TestResult) -> None:
    try:
        alert = page.get_by_role("alert").locator("div").filter(has_text="Berhasil Masuk")
        await alert.wait_for(timeout=config.timeout_ms)
        result.add_log("Login successful: 'Berhasil Masuk' alert found.")
    except TimeoutError:
        result.add_log("Login failed: Alert with 'Berhasil Masuk' not found.", "FAILED")


async def take_screenshot(page, screenshot_path: Path) -> None:
    await page.screenshot(path=str(screenshot_path))
    print(f"Screenshot saved to {screenshot_path}")


async def main() -> None:
    login_config = LoginTestConfig()
    email_config = EmailConfig()

    try:
        result = await run_login_test(login_config)
    except TimeoutError as error:
        print(f"Test stopped because required step timed out: {error}")
        result = TestResult(passed=False)
        result.add_log("Test stopped because required step timed out.", "FAILED")

    PdfReport().generate(result, login_config.screenshot_path, login_config.report_path)
    EmailSender(email_config).send_attachment(login_config.report_path)


if __name__ == "__main__":
    asyncio.run(main())
