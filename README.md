# Tech Talks with Manju — Free Cloud Shorts Renderer

This repository contains a simple narrated YouTube Shorts MP4 renderer deployed as a Render web service.

- POST /render with a topic, title, voiceover, and optional brand; request must include the `x-render-key` header.
- GET /health returns readiness.
- Generates a 540 × 960 MP4 using eSpeak NG, Pillow and FFmpeg.
- No paid TTS/video API, no Google or YouTube tokens stored here.
- This is a slide-based narrated prototype; it is not cinematic AI video.

## Deploy
1. Render > New > Web Service > Connect this GitHub repository.
2. Language/runtime: **Docker**. Instance type: **Free**.
3. Name: `techtalks-shorts-renderer`; root directory: repository root; Dockerfile: `./Dockerfile`.
4. Set the `RENDER_SECRET` environment variable to a **long random private value** (32+ characters). Never put it in the repository.
5. Health-check path: `/health`.
6. Deploy; then open `https://YOUR-SERVICE.onrender.com/health`.
7. In n8n Cloud, set the rendering URL to `https://YOUR-SERVICE.onrender.com/render` and set a **Header Auth** credential (`x-render-key` = same `RENDER_SECRET`).
8. Connect Google Sheets, Google Drive and YouTube credentials *inside n8n*, test an upload as **Private**, then enable the schedule.

Example JSON body:
```json
{"topic":"What is n8n?","title":"n8n in 60 Seconds","voiceover":"n8n lets you connect apps and automate tasks with simple visual workflows. Start with a trigger, connect a service, and see the results.","brand":"Tech Talks with Manju"}
```

Render Free sleeps when idle, so cold starts and resource limits may interfere with long video renders. Keep uploads private until tested.
