## 2024-03-04 - Playwright Network Interception for Speed
**Learning:** Google Gemini UI loads an immense amount of heavy assets (fonts, avatars, media) that are completely unnecessary for pure text automation. These static assets delay the page from reaching the `networkidle` state, forcing the bot to wait longer than necessary before it can interact with the DOM or extract text.
**Action:** Always implement `page.route("**/*")` to intercept and abort requests with `resource_type` of `image`, `media`, or `font` when building text-only Playwright automation scripts against heavy SPAs.
