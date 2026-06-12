import asyncio
from playwright.async_api import async_playwright, TimeoutError
import matplotlib.pyplot as plt
from fpdf import FPDF
import tempfile
from mailjet_rest import Client
import base64


def generate_pdf_report(logs, test_passed, screenshot_path, output_file="test_report.pdf"):
    """Generate a visually appealing PDF report with tables and charts."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    # Add Title
    pdf.set_font("Arial", style="B", size=16)
    pdf.cell(200, 10, txt="Test Report", ln=True, align='C')
    pdf.ln(10)

    # Add Summary
    pdf.set_font("Arial", size=12)
    status = "Test Passed" if test_passed else "Test Failed"
    pdf.cell(0, 10, txt=f"Overall Test Status: {status}", ln=True)
    pdf.ln(5)

    # Generate and add a summary chart
    success_count = sum(1 for log in logs if log["status"] == "PASSED")
    failed_count = sum(1 for log in logs if log["status"] == "FAILED")

    plt.figure(figsize=(4, 4))
    plt.pie(
        [success_count, failed_count],
        labels=["Passed", "Failed"],
        autopct='%1.1f%%',
        colors=["#4CAF50", "#FF5252"],
        startangle=140,
    )
    plt.title("Test Result Summary")

    # Save chart to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmpfile:
        chart_path = tmpfile.name
        plt.savefig(chart_path)

    # Add chart to PDF
    pdf.image(chart_path, x=60, y=50, w=90)
    pdf.ln(80)

    # Add Detailed Logs Table
    pdf.set_font("Arial", style="B", size=12)
    pdf.cell(0, 10, txt="Detailed Test Logs:", ln=True)
    pdf.ln(5)

    pdf.set_font("Arial", size=10)
    pdf.set_fill_color(200, 200, 200)
    pdf.cell(120, 10, txt="Log Message", border=1, align="C", fill=True)
    pdf.cell(40, 10, txt="Status", border=1, align="C", fill=True)
    pdf.ln()

    for log in logs:
        pdf.cell(120, 10, txt=log["message"], border=1)
        pdf.cell(40, 10, txt=log["status"], border=1, align="C")
        pdf.ln()

    # Add Evidence Testing Section
    pdf.add_page()
    pdf.set_font("Arial", style="B", size=14)
    pdf.cell(0, 10, txt="Evidence Testing:", ln=True, align="L")
    pdf.ln(10)

    if screenshot_path:
        pdf.image(screenshot_path, x=20, y=30, w=170)
        pdf.ln(90)  # Add space after the image
    else:
        pdf.cell(0, 10, txt="No evidence available.", ln=True)

    # Save the PDF
    pdf.output(output_file)
    print(f"PDF report generated: {output_file}")



def send_email_with_attachment(to_email, subject, body, attachment_path):
    """Send an email with an attachment using Mailjet."""
    api_key = '3ba0a39828b9bcfdd8b17f45ab66dab8'  # Replace with your Mailjet API Key
    api_secret = '41218dad17156b27ad93dfc2803e0a5a'  # Replace with your Mailjet API Secret
    mailjet = Client(auth=(api_key, api_secret), version='v3.1')

    # Open the file and encode it as base64
    with open(attachment_path, "rb") as file:
        encoded_file = base64.b64encode(file.read()).decode("utf-8")

    data = {
        'Messages': [
            {
                'From': {
                    'Email': 'siswa5.siswamedia@gmail.com',  # Replace with your email
                    'Name': 'Siswamedia Report Test'  # Replace with your name
                },
                'To': [
                    {
                        'Email': to_email,  # Replace with the recipient's email
                        'Name': 'Recipient Name'  # Replace with recipient's name
                    }
                ],
                'Subject': subject,
                'TextPart': body,
                'Attachments': [
                    {
                        'ContentType': 'application/pdf',
                        'Filename': 'test_report.pdf',
                        'Base64Content': encoded_file
                    }
                ]
            }
        ]
    }

    result = mailjet.send.create(data=data)
    print(f"Email sent status: {result.status_code}")


async def run(playwright):
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()

    logs = []
    test_passed = True

    # Add log helper function
    def add_log(message, status="PASSED"):
        nonlocal test_passed
        logs.append({"message": message, "status": status})
        if status == "FAILED":
            test_passed = False
        print(f"{status}: {message}")

    # Navigate to the login page
    try:
        await page.goto("https://app.siswamedia.com/login", timeout=5000)
        add_log("Successfully navigated to the login page.")
    except TimeoutError:
        add_log("Timeout: Failed to load login page within 5 seconds.", status="FAILED")
        await browser.close()
        return

    # Interact with the login form
    try:
        await page.get_by_text("Masukan ID Pengguna").click(timeout=5000)
        add_log("Clicked on 'Masukan ID Pengguna'.")

        await page.get_by_placeholder("ID Pengguna / Email").click(timeout=5000)
        await page.get_by_placeholder("ID Pengguna / Email").fill("siswa1.siswamedia@gmail.com", timeout=5000)
        add_log("Filled 'ID Pengguna / Email'.")

        await page.get_by_placeholder("Kata Sandi").click(timeout=5000)
        await page.get_by_placeholder("Kata Sandi").fill("Kiasu123", timeout=5000)
        add_log("Filled 'Kata Sandi'.")

        await page.get_by_role("button", name="Masuk").click(timeout=5000)
        add_log("Clicked on 'Masuk' button.")
    except TimeoutError:
        add_log("Timeout: Interaction with the login form took too long.", status="FAILED")
        await browser.close()
        return

    # Validate the alert text after successful login
    try:
        alert_locator = page.get_by_role("alert").locator("div").filter(has_text="Berhasil Masuk")
        await alert_locator.wait_for(timeout=5000)
        add_log("Login successful: 'Berhasil Masuk' alert found.")
    except TimeoutError:
        add_log("Login failed: Alert with 'Berhasil Masuk' not found.", status="FAILED")

    await asyncio.sleep(3)

    # Take a screenshot
    screenshot_path = "screenshot1.png"
    await page.screenshot(path=screenshot_path)
    print(f"Screenshot saved to {screenshot_path}")

    # Close the context and browser
    await context.close()
    await browser.close()

    return logs, test_passed


async def main():
    async with async_playwright() as playwright:
        logs, test_passed = await run(playwright)
        screenshot_path = "screenshot1.png"  # Path ke screenshot
        pdf_file = "test_report.pdf"
        generate_pdf_report(logs, test_passed, screenshot_path, pdf_file)  # Generate the PDF report
        send_email_with_attachment(
            to_email="354risyad@gmail.com",  # Replace with the recipient's email
            subject="Test Report",
            body="Please find the attached test report.",
            attachment_path=pdf_file
        )


# Run the async main function
asyncio.run(main())