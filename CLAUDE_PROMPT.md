# YouTube to MP3 Converter UI/UX Upgrade Handoff

Hello Claude! I am currently working on a YouTube to MP3 converter project. The backend functionality and deployment are fully complete and stable, but I need your help to upgrade the frontend UI/UX design.

Here is the current state of the project and the rules for your design updates:

## 1. Project Architecture
- **Backend:** Python Flask + `yt-dlp` (Extracts audio via FFmpeg).
- **Frontend:** Vanilla HTML/CSS/JS (contained within `templates/index.html`).
- **Communication:**
  - POST `/convert`: Accepts `{"url": "youtube_url"}` and returns a `job_id`.
  - GET `/progress/<job_id>`: Server-Sent Events (SSE) endpoint that streams conversion progress (status, percent, speed, eta, error).
- **Deployment:** Render.com (URL: `https://luckymusic-mp3.onrender.com`).

## 2. Core Frontend Features (MUST PRESERVE)
The current frontend has some critical functional logic that you **must not break** when redesigning the UI:
- **Clipboard Auto-Paste:** If the URL input is empty when the 'Convert' button is clicked, `navigator.clipboard.readText()` automatically fetches the URL and starts the download.
- **SSE Progress Bar:** The UI dynamically updates a progress bar using `EventSource` based on the backend streaming data.
- **Dynamic Status Messages:** Text updates to show "Downloading (x%)", "Converting...", and "Done!".

## 3. Your Task: UI/UX Redesign
Please redesign the `templates/index.html` file to make it look modern, premium, and highly responsive. You have creative freedom over the CSS and layout, but please follow these guidelines:

### Design Requirements:
- **Aesthetic:** Modern, sleek, "glassmorphism" or neo-brutalism style. Dark mode support would be great.
- **Animations:** Add smooth transitions for the progress bar, button hover states, and loading spinners.
- **Responsiveness:** Ensure it looks perfect on mobile devices (the primary use case).
- **Framework:** Please stick to Vanilla CSS (no Tailwind or external heavy libraries) to keep it lightweight, or suggest a lightweight CSS framework if absolutely necessary.
- **Error Handling UI:** Make error messages (e.g., "Invalid URL", "Clipboard access denied") look elegant rather than using the default browser `alert()`.

### Constraints:
- Do NOT change the backend `app.py`.
- Do NOT alter the endpoint URLs (`/convert`, `/progress/<job_id>`).
- Do NOT remove the clipboard read logic in the JavaScript.

Please provide the completely updated `templates/index.html` code based on these instructions!
