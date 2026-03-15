# Gemini Automation Chain Builder & App Store

The **Gemini Automation Chain Builder** is a powerful visual Multi-Agent workflow builder tailored explicitly for Google's Gemini models. It allows you to orchestrate web scrapers, data parsers, and nested conversational agents through a React Flow DAG (Directed Acyclic Graph) interface.

With **V22.0 (The AI App Store)**, you can now seamlessly publish your complex developer workflows as clean, Coze/ChatGPT-style minimalist applications for end-users to consume directly via Magic Forms!

## ✨ Features
- **Visual DAG Editor:** Drag-and-drop React Flow interface for designing Agentic Pipelines.
- **Agentic Loops:** Implement self-correcting or iterative tasks between Gemini and standard browser scrapers.
- **The AI App Store:** Publish developer blueprints as user-friendly apps with dynamic input forms.
- **Multimodal Attachments:** Directly attach PDFs, Images, or CSVs to specific Gemini prompts.
- **Account Profiles:** Manage independent browser persistence contexts (Work vs. Personal).
- **Global Variables & State Management:** Easily pass {{NODE_ID}} references to downstream nodes.

---

## 🚀 Getting Started

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)
- Google Chrome installed locally

### 1. Environment Setup

First, initialize the Python backend (FastAPI + Playwright):
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Next, initialize the Next.js frontend and Prisma database:
```bash
npm install
npx prisma db push
npx prisma generate
```

### 2. Running the Servers

Start the Python FastAPI Engine:
```bash
uvicorn app:app --host 0.0.0.0 --port 8000 &
```

In a separate terminal, start the Next.js frontend:
```bash
npm run dev &
```

Visit `http://localhost:3000` in your browser.

---

## 🔑 Authentication (Account Manager)
The core engine relies on a headless Chromium browser instance interacting directly with Gemini's web interface (to avoid API costs and leverage advanced features).

**To use the platform, you must first log in:**
1. Open the **Gemini Builder** at `http://localhost:3000`.
2. Click the `[ 👤 Accounts ]` button in the top-left sidebar.
3. Enter a Profile ID (e.g., `1` or `work`) and click **Launch Headful Browser**.
4. A Chromium window will appear. Manually log into your Google Account.
5. Close the browser window. Your session cookies are now securely saved in `chrome_profile_{id}` for headless use!

---

## 🛠️ Building Workflows

### Node Types
* **Trigger:** Initiates the workflow (Manual or Cron-based).
* **Gemini AI:** Sends prompts to Gemini. Supports Model Selection (Flash vs. Pro) and File Attachments.
* **Web Scraper:** Extracts text from any target URL to use in downstream analysis.
* **Agent Loop:** Creates a bounded retry/iteration loop. Set `Max Iterations` to prevent runaways.
* **Global State:** Stores variables (`{{PROJECT_GOAL}}`) accessible anywhere in the DAG.

### Variable Binding
When writing prompts in the Gemini AI node, you can dynamically inject upstream data using tags. Click the `[ Insert Variable ]` dropdown or manually type `{{NODE_ID}}` (where NODE_ID is the specific ID of a previous step, e.g., `{{1719283719}}`).

### Publishing to the App Store
1. Build a functional workflow in your workspace.
2. Leave required fields empty (e.g., an empty Target URL in a Web Scraper).
3. Click `🚀 Publish App` in the top right.
4. Go to the Dashboard (by deselecting your workspace). Your new application is now available as a clean "Magic Form" for anyone to use!

---

## ⚠️ Troubleshooting

**Q: The execution terminal says "Missing X server or $DISPLAY"**
* Playwright is attempting to launch a headful browser in a headless server environment (like Docker or WSL without X11). Ensure `HEADLESS_MODE=True` is set in your environment or via the UI settings when not actively logging in.

**Q: "TargetClosedError" or "Memory Overload"**
* You ran out of system RAM or Chromium crashed. The backend auto-recovers and resets the context, but you may need to reduce your `Max Iterations` in Agent Loops or increase your server memory.

**Q: My attachments aren't uploading!**
* The file upload logic relies on the Gemini DOM structure. If Google updates the UI, the Playwright selectors in `bot.py` (`button[aria-label*='Upload image']`) may need updating.
