# On-camera behavioral analysis (mock interview)

When a live session ends, up to **12 JPEG snapshots** from the candidate camera are sent to vision AI (not stored). The model scores **55 parameters** in nine categories:

1. **Eye contact & gaze** (1–5) — camera gaze, stability, screen attention, shift frequency, head orientation  
2. **Facial expression & engagement** (6–10) — visibility, variation, smile frequency, engagement cues, expression-context alignment  
3. **Posture & body language** (11–15) — upright posture, stability, head movement, body orientation, excessive movement  
4. **Hand gestures & movement** (16–20) — frequency, visibility, repetition, distraction, gesture-speech timing  
5. **Camera presence & video quality** (21–25) — face in frame, distance, lighting, stability, A/V sync (limited from stills)  
6. **Prohibited activities** (26–33) — smoking/vaping, eating, drinking, phone/secondary devices, assistance, leaving frame, obstruction  
7. **Distracting / unprofessional behaviors** (34–43) — hair/face/nose/beard/clothing/accessory adjustments, fidgeting, etc.  
8. **Interview integrity concerns** (44–50) — off-screen glances, suspected reading, notes, multiple people, external help  
9. **Camera / feed integrity events** (51–55) — face disappearance, feed interruption, environment changes  

Parameters marked **audio-only** in the backend catalog (e.g. off-camera voice, repeated muting) return `not_observable` from stills alone.

Results appear on the report under **On-camera behavior**, in **Export PDF**, and drive **professional conduct** flags (including smoking) and rubric **Professional etiquette** (#74) when concerns are detected.

See [MOCK_INTERVIEW.md](./MOCK_INTERVIEW.md) for camera capture timing and privacy.
