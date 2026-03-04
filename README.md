# Gemini Workflow Builder

Automation of input and output of Gemini using FastAPI and Playwright.

## Features

- **Visual Workflow Builder:** Create multi-step workflows with ease.
- **Smart Context Injection:** Use `{{OUTPUT_X}}` to pass the results of one step to the next.
- **Data Iteration (Batch List):** Process multiple inputs iteratively by defining a "Batch List" step and using `{{CURRENT_ITEM}}` in subsequent prompts. You can even import CSV/Text files to populate the list.
- **Built-in Templates:** Quickly load pre-defined workflows like "Batch Translate" and "Viral Titles".
- **Real-time Feedback:** Server-Sent Events (SSE) provide live updates, a global progress bar, and visual highlighting of the currently executing step.
- **Robust Automation:** Utilizes dual-state checking and network interception to ensure reliable and fast interactions with Gemini.
- **File Uploads:** Automatically uploads files associated with your workflow data.

## Getting Started

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

2.  **Run the application:**
    ```bash
    uvicorn app:app --host 0.0.0.0 --port 5000
    ```

3.  **Access the Builder:**
    Open your browser and navigate to `http://localhost:5000`.

## Playwright Async Architecture

This project maintains a strict asynchronous architecture using `playwright.async_api`. This ensures that the FastAPI event loop is never blocked by browser automation tasks, allowing for efficient handling of SSE streams and concurrent requests. The `bot_lock` prevents multiple workflows from interfering with a single browser instance.