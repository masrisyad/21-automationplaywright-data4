# Automated Test: Kelasku Info Deletion & Reporting

This project is an automated testing script built with Python and **Playwright**. It performs an end-to-end UI test that logs into a web application, navigates to the "Kelasku" (My Class) module, and attempts to delete an existing informational post.

The script features a smart fallback mechanism: if it cannot immediately find the delete button, it will open the class details first and try again. Finally, it generates a comprehensive PDF report with visual evidence and automatically emails it to the team via the Mailjet API.

---

## 🌟 Key Features

* **Resilient UI Automation:** Asynchronously interacts with the web page, handles loading spinners, and gracefully falls back to alternative UI selectors if primary elements are hidden or missing.
* **Smart Deletion Logic:** Attempts to click delete/trash icons directly; if unsuccessful, it opens the class details to locate the delete button and automatically handles confirmation dialogs.
* **Dynamic PDF Reporting:** Compiles a professional PDF test report using `fpdf` and `matplotlib` that includes:
* A pass/fail summary donut chart.
* A detailed step-by-step log table.
* A screenshot of the browser at the end of the test.


* **Automated Email Integration:** Seamlessly sends the generated PDF report as an email attachment using Mailjet.

---

## 📋 Prerequisites

Ensure you have **Python 3.8+** installed on your machine. You will also need to install the required third-party libraries.

### Required Installations

Run the following command in your terminal to install the Python dependencies:

```bash
pip install playwright matplotlib fpdf2 mailjet_rest

```

Playwright requires browser binaries to function. Install the Chromium browser by running:

```bash
playwright install chromium

```

---

## ⚙️ Configuration

This script relies on environment variables and an external `settings.py` file to manage credentials and test behaviors safely.

### 1. Environment Variables

You can customize the script's behavior by configuring the following environment variables:

| Variable Name | Description | Default Value |
| --- | --- | --- |
| `WAIT_AFTER_ACTION_SECONDS` | Time to wait (in seconds) before taking the final screenshot. | `3` |
| `SCREENSHOT_PATH` | The file name and path for the saved visual evidence. | `screenshot4_kelasku_info_delete.png` |
| `REPORT_PATH` | The file name and path for the generated PDF report. | `test_report_kelasku_info_delete.pdf` |

### 2. The `settings.py` File

The script imports `EmailConfig` and `LoginConfig` from a local file named `settings.py`. You must create this file in the same directory as your script. Here is an example of the required structure:

```python
# settings.py
from dataclasses import dataclass
import os

@dataclass
class LoginConfig:
    login_url: str = "https://your-website.com/login"
    username: str = "your_email@example.com"
    password: str = "your_password"
    timeout_ms: int = 15000
    headless: bool = True  # Set to False to watch the browser in action

@dataclass
class EmailConfig:
    enabled: bool = os.getenv("SEND_EMAIL", "false").lower() == "true"
    api_key: str = os.getenv("MAILJET_API_KEY", "")
    api_secret: str = os.getenv("MAILJET_API_SECRET", "")
    sender_email: str = "sender@example.com"
    sender_name: str = "Automated QA"
    recipient_email: str = "team@example.com"
    recipient_name: str = "Dev Team"
    subject: str = "Kelasku Info Delete Test Report"
    body: str = "Please find the attached automated test report for the deletion module."

```

---

## 🚀 Usage

Once your dependencies are installed and your configuration is set, run the test script from your terminal:

```bash
python main.py

```

*(Assuming you saved the provided script as `main.py`)*

### Execution Flow:

1. Launches a headless Chromium browser instance.
2. Logs into the application using credentials from `settings.py`.
3. Navigates to the **Kelasku** menu.
4. Searches for a delete/trash icon to remove an entry.
5. Handles deletion confirmations automatically.
6. Captures a screenshot of the final result.
7. Generates the PDF report and dispatches the email.

---

## 📂 Output Files

Upon completion, the script generates the following files in your project directory:

* **Visual Evidence:** `screenshot4_kelasku_info_delete.png` (Shows the final state of the web page).
* **Test Report:** `test_report_kelasku_info_delete.pdf` (Contains the pass/fail graph, detailed logs, and the screenshot).
