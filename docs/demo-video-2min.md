# 2-minute demo video: recording script and motion brief

Two parts:

- **Part A** is for recording. It covers setup and a list of shots, each with the exact taps to make.
- **Part B** is for the motion-design pass. It covers timings, voice-over, on-screen text, callouts and cuts for each shot.

Record each shot as its own clip, named as in the table (`S03_advisor.mp4` and so on). Long waits are fine: Part B says where to cut them.

Story: **Joseph runs Harmony Dental Care in Kolkata.** He speaks Hindi to the advisor and gets one plan with one price. His first upload is wrong (another business's stale documents) and gets caught. His real documents verify, and then he signs and tracks the order. Sales gets the leads the advisor couldn't close.

---

## Part A: recording

### Before you record (10 minutes)

1. **Site.** Use `https://airtel-sync-2026.vercel.app` (dev). Once `dev` is merged into `prod`, `https://airtel-sync-26.vercel.app` works too.
2. **Clear the saved app copy.** Open DevTools → Application → Service workers, click **Unregister**, then go to **Storage** and click **Clear site data**. Reload twice.
3. **Wake the backend.** Open `https://udyam-api-dev.onrender.com/health` and wait for `"ok": true`. Do this about 1 minute before recording, because a sleeping server takes about 50 seconds to answer the first request.
4. **Seed the back-office** so S09 has a live hand-off at the top. Run one quick journey, then close the tab:
   - Start, then type `I run a travel agency in Visakhapatnam, 4 staff, have GST`.
   - Accept the plan and the consent.
   - In **Use a sample**, tap **K01**, then **Verify now**.
   - The cancelled GSTIN sends it to a person.
5. **Browser view:**
   - Device toolbar on, **390 × 844**, zoom 100%, touch emulation on, so taps show as a circle.
   - Dock DevTools to a separate window so the phone view is clean.
   - Light mode. Close other tabs and turn on Windows Focus Assist so no notifications appear.
6. **Recorder:**
   - Use OBS, or the Snipping Tool's video mode (Win + Shift + R).
   - Record only the phone viewport, at 60 fps if possible. Don't record audio; the voice-over is added later.
7. **Expect waits:**
   - The document reader handles about 3 photos a minute on the free tier, so the 8 photos in S06 take about 3 minutes. Keep recording through it.
   - If the mic or Groq is slow in S03, type the sentence instead.

**For every clip:** hold still for **1 second before and after** each action, and don't move the cursor during waits. Those still frames are what transitions and zooms are built on.

### Shot list

| Clip | Screen | Do exactly this |
|---|---|---|
| `S02_home.mp4` | Home | Start on the hero. Tap **हिन्दी**, then wait until the page is in Hindi. Tap **शुरू करें: 3 मिनट लगेंगे**. |
| `S03_advisor.mp4` | Advisor (Hindi) | Tap 🎤 and say: *"मेरा डेंटल क्लिनिक है कोलकाता में, 8 लोग काम करते हैं, GST है"*. Tap 🎤 again to stop. Wait for the reply. If it asks one more question, answer with a chip. Stop when the **plan** appears. |
| `S04_plan.mp4` | Plan | 1. Switch the header language dropdown to **English** and hold for 1 second on the English plan.<br>2. Tap the **24 months** contract.<br>3. Turn **Backup 4G/5G Failover** on.<br>4. Tick **Spread setup over 6 months**.<br>5. Scroll slowly to **Why this plan** and hold.<br>6. Tap **Continue**. |
| `S05_consent.mp4` | Consent | Tick the two **Required** purposes, leave marketing unticked, and tap **Agree and continue**. |
| `S06a_kyc_lookup.mp4` | Verify | In the GSTIN box, type `37IHKXV5167L1ZS` (K01) and hold on the red **Cancelled** line for 2 seconds. Clear the box. |
| `S06b_kyc_wrong.mp4` | Verify | Open **Use a sample**, tap **K11**, wait until all 4 documents are read, then tap **Verify now**. Hold on **A few things to fix** and scroll through it slowly. |
| `S06c_kyc_right.mp4` | Verify | Tap **K02**, wait until all 4 documents are read, then tap **Verify now**. Hold on the green result for 2 seconds. |
| `S07_sign.mp4` | Sign | Pick the first installation slot, type OTP `123456`, and tap **Sign and place order**. |
| `S08_tracker.mp4` | Tracker | Hold on the timeline. Tap **Demo: next step** twice, pausing 1 second after each tap. Type *"When will my internet start?"*, tap **Ask**, and hold on the answer. |
| `S09_backoffice.mp4` | Back-office | Open `/backoffice`, enter key `demo`, and tap **Open**. Hold on the four stat tiles. Scroll to the leads list and stop on the K01 hand-off at the top. Tap **Partner: nearest store** and hold on **Assigned to…**. |

S01 and S10 are title cards and need no recording.

If something odd happens mid-take (a slow reply, a typo), keep going. Just redo that one clip.

---

## Part B: motion brief

**Format:** 1920 × 1080, 30 or 60 fps, final length **2:00**. Place the phone recording in a device frame on the right two-thirds of the screen, with supers and callouts on the left. Each clip from Part A gets its own shot.

**Brand:**

| Element | Value |
|---|---|
| Background | `#fffaf7` |
| Primary | `#d7261e` (dark `#a81b15`, soft `#fdecea`) |
| Ink | `#1d1b1a` |
| Muted | `#6b6461` |
| Good | `#15803d` |
| Bad | `#b91c1c` |
| Font | Inter (Noto Sans Devanagari for Hindi) |

**Style:**
- Clean, calm motion with 200–300 ms ease-out moves.
- Zoom-ins of 1.4–1.8× onto the element being tapped.
- A soft red ring pulse on each tap.
- No whooshes or glitch effects.

**Voice-over:** about 255 words at a calm pace (around 130 words per minute). The lines below are timed to fit.

| # | Time | Clip | Voice-over | Supers / callouts | Motion and cuts |
|---|---|---|---|---|---|
| S01 | 0:00–0:06 | Title card | "Accel Business converts 7% of small-business leads. Activation takes 17.6 days, and customers call three times to chase it." | Three big numbers count up in sequence: **7%** leads activate · **17.6 days** to activate · **3** status calls. Subline: *"Today's SMB journey"*. | Numbers count up and stagger in. End with them sliding left, out of frame. |
| S02 | 0:06–0:12 | `S02_home` | "Udyam Digital does it in one sitting, in the owner's language." | Logo lock-up **Udyam Digital**, then the tagline *"One plan. One bill. Activated in days."* | Phone frame slides in from the right. Zoom onto the **हिन्दी** chip as it's tapped. |
| S03 | 0:12–0:34 | `S03_advisor` | "Joseph runs a dental clinic in Kolkata. He just says it in Hindi. Our AI advisor picks out his business, size, city and GST status, and asks only what's missing. The language model talks; our rules engine picks the products and prices, so nothing is made up." | English subtitle under the Hindi speech: *"I have a dental clinic in Kolkata, 8 people work there, I have GST"*. Callout tags pop in beside the phone as the fields are understood: `Business: dental clinic` · `City: Kolkata` · `8 staff` · `GSTIN ✓`. Small badge: *Groq · rotates models on rate limits*. | **Cut the wait** between the end of the speech and the reply, leaving 0.5 s. Speed up any typing 2×. |
| S04 | 0:34–0:50 | `S04_plan` | "One plan, one monthly price with GST shown, and setup spread over six months. Switching on backup internet adds its dependencies automatically, and the price updates live." | Callout on the price: **One monthly price · GST shown**. Callout on the toggle: **Dependencies added automatically**. Brief label at the language switch: *Switch language any time; nothing is lost*. | Zoom onto the price each time it changes, and show the old and new values with a quick roll. Trim the scroll to about 2 s. |
| S05 | 0:50–0:56 | `S05_consent` | "Consent is asked per purpose, as the DPDP Act requires. Marketing stays off unless he opts in." | **Consent per purpose · DPDP Act 2023**. Marker: *Marketing: off by default*. | Fast. Speed up to 1.5× if needed. |
| S06a | 0:56–1:02 | `S06a_kyc_lookup` | "Registration numbers are checked against the registries as he types." | Red callout pointing at the line: **Cancelled GSTIN caught instantly**. | Zoom on the GSTIN field and the result line. |
| S06b | 1:02–1:15 | `S06b_kyc_wrong` | "Upload the wrong papers, and Smart KYC explains exactly what's wrong in plain words: a bill that's too old, or a signatory who can't sign for a company." | Callout list next to the phone, ticking in one by one in red: **Bill older than 90 days** · **'Owner' can't sign for a Pvt Ltd** · plus any other checks shown. Small badge: *Photos deleted after reading*. | **Cut the reading wait** (about 1.5 min) down to a 1 s "Reading 4 documents…" progress card. Zoom into the **A few things to fix** panel. |
| S06c | 1:15–1:24 | `S06c_kyc_right` | "With the right documents, every check passes: registry, names, address, bill date and who signs." | A green check stack animates in: **GSTIN valid & active** · **Names match registry** · **Address matches** · **Bill is recent** · **Proprietor signs**. | **Cut the reading wait** the same way. End on the green state, scaled up slightly. |
| S07 | 1:24–1:33 | `S07_sign` | "He signs with an OTP and picks an installation slot. That's the whole application." | **e-Sign with OTP · Pick your slot**. | Speed up the OTP typing 2×. |
| S08 | 1:33–1:45 | `S08_tracker` | "Instead of calling to chase status, he sees every step, gets WhatsApp-style updates, and can ask about his order in his own words." | Callout: **No status calls**. Show the question and answer as a chat bubble overlay, larger than in the app. | Each tap on **Demo: next step** gets a tick animation on the timeline. Cut the answer wait to 0.5 s. |
| S09 | 1:45–1:56 | `S09_backoffice` | "Anything the advisor can't close goes to sales and partners, ranked by likelihood to activate, with the next best action. Partners earn on assisted journeys, so digital works with them, not against them." | Callouts: **Ranked by activation likelihood** · **Next best action** · **Partner gets the lead**. | Zoom on the top lead card, then on **Assigned to…**. |
| S10 | 1:56–2:00 | End card | "One plan. One bill. Activated in days." | Logo, tagline, and the URL `airtel-sync-26.vercel.app`. Small line: *YTL Hackathon 2026 · Track A · Accel Telecom is fictional · all data synthetic*. | Fade out to the background colour. |

**Music:** soft, warm, low-tempo bed at about −24 LUFS under the voice-over. Duck it a further 6 dB while the Hindi line in S03 plays.

**Captions:** burn in English captions for the whole voice-over, bottom-left, Inter 600, white on 70% ink.

**If over time, trim in this order:**
1. Drop S06a.
2. Shorten S05 to 4 s.
3. Remove the scroll to **Why this plan** in S04.

Never cut S06b: catching a planted problem is the core of the Smart KYC ask.
