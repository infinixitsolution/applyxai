# Mock interviews (candidate)

Voice-driven practice interviews tied to an **application** (job + resume context). Requires platform AI with the **mock_interview** feature enabled and an OpenAI-compatible provider for Whisper/TTS.

A **valid API key** must be saved under **Admin → Settings → AI** (use **Test AI** after saving). A missing or wrong key surfaces as `401` / `AI_AUTH_FAILED` when the interview starts.

## Database

Apply migrations **0025–0026** (and any earlier pending revisions) before using this feature:

```bash
python -m alembic -c backend/alembic.ini upgrade head
```

Without it, `POST /api/mock-interviews/sessions` returns `500 INTERNAL_ERROR`.

## Browser support

- **Layout:** Live session uses a **two-panel** view (AI interviewer + your camera preview), similar to a video call.
- **Speech-to-text:** Chrome or Edge (Web Speech API) with **hands-free** mode — speak naturally; mid-sentence pauses are OK. We wait ~2.5–4 seconds of silence (or tap **Done speaking**) before sending your answer. Other browsers can record audio and use server **Whisper** via `POST /api/mock-interviews/transcribe` when you tap **Done speaking**.
- **Camera:** Recommended; JPEG stills are captured about every 40 seconds and after each answer (up to 12 frames) and analyzed when you end the interview for expression, eye contact, grooming, and **professional conduct** (e.g. smoking or vaping on camera). Still images are **not** stored—only scores/notes in your feedback JSON.
- **Microphone:** Required for voice mode; allow permission when prompted.
- **Real-time turns:** Turn and opening APIs return interviewer text first (`include_audio=false`); voice plays via `POST /api/mock-interviews/sessions/{id}/messages/{message_id}/tts` (browser speech is fallback only if TTS fails). Send `client_turn_id` (UUID) on turns to safely retry after network errors.
- **Feedback jobs:** `POST .../complete` and `.../regenerate-feedback` enqueue analysis (HTTP **202** + `job_id` when Celery is running; inline fallback when Redis is unavailable). Poll `GET /api/mock-interviews/feedback-jobs/{job_id}` until `status` is `succeeded` or `failed`.
- **On-camera behavior:** 55-parameter vision analysis from session snapshots — see [MOCK_INTERVIEW_BEHAVIOR.md](./MOCK_INTERVIEW_BEHAVIOR.md).
- **Interviewer voice:** Indian English **female** profile (`shimmer` + `gpt-4o-mini-tts` with accent/pace instructions). Admins can override `mock_interview_voice` in platform AI JSON (voice, speed, instructions, models).
- **Live UX:** **Barge-in** — start speaking while the interviewer is talking (mic unmuted) to cut off TTS and take your turn; or tap **Interrupt**. **Replay** replays the last interviewer question (cached server TTS when available).
- **Presenter:** Default `digital_human_3d` with **`glb_url: /portrait`** — studio portrait in a Three.js scene (exact photo likeness + subtle voice motion). Set **`glb_url`** to a `.glb` path for a rigged avatar instead. **Photo URL** drives the portrait texture. Optional **CC**, **Replay**, **barge-in** / **Interrupt**. Fallback: `static_photo` or `live_stream` URL in Admin → Platform AI → Mock interview presenter.

## Flow

1. Candidate picks an application and interview types (`behavioral`, `technical`, `hr`, or `mixed`) at `/app/mock-interview`. Questions are grounded in that application’s **job description** and **attached resume** (companies, projects, skills); the backend builds a JD ↔ resume question plan so the interviewer stays on-role rather than generic trivia.
2. Live session at `/app/mock-interview/:sessionId` — opening line, then hands-free voice turns. A **30-minute** countdown runs from session start; at zero the app auto-ends and generates feedback.
3. **End & get report** (or auto at time limit) runs the full analysis pipeline: transcript coaching, **100-parameter answer rubric**, **55-parameter on-camera behavior** (from up to 12 snapshots), presentation summary, and answer authenticity. Progress is shown while the server works (~30–90s). The report lives at `/app/mock-interview/:sessionId/report`. **Regenerate analysis** re-runs text/rubric/coaching from the saved transcript (camera frames are not kept—vision sections need the original end-of-session run). **Export PDF** downloads the complete report including behavior tables and transcript.

## Privacy

- Transcripts and feedback JSON are stored per user in `mock_interview_sessions` / `mock_interview_messages`.
- Audio is not persisted; only text transcripts are kept.

## Limits

- **30 minutes** wall-clock per session (`max_duration_seconds: 1800`, `ends_at` on session API).
- Up to 12 candidate answers per session (configurable in backend prompts).
- Rate limits: session create `10/hour`, turns `30/minute`, transcribe `20/minute` per user.

See [API.md](./API.md#mock-interviews) for endpoints and feedback schema. Implementation checklist: [MOCK_INTERVIEW_IMPLEMENTATION_PLAN.md](./MOCK_INTERVIEW_IMPLEMENTATION_PLAN.md).
