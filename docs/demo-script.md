# 3-minute demo script

Record on a phone-sized browser (Chrome DevTools, 390×844) or a real phone pointed at the production URL. Open the back-office in a second tab beforehand.

| Time | Screen | Action | Voice-over |
|---|---|---|---|
| 0:00–0:15 | Home | Show the hero, then tap **हिन्दी** | "7% of SMB leads activate today, after 17.6 days and three status-chasing calls. Udyam Digital does it in one sitting, in the owner's language." |
| 0:15–0:50 | Advisor | Tap 🎤 and say *"मेरा डेंटल क्लिनिक है पुणे में, 8 लोग हैं, GST है"*. Answer the one remaining question with a chip. | "The advisor runs on Groq. If a model hits its rate limit we rotate to the next one, and if all are down a scripted advisor takes over. Products and prices always come from the rules engine, never the LLM." |
| 0:50–1:20 | Quote | Toggle **Backup 4G failover** on, switch to **24 months**, then show the price and GST update. Point at the locked item showing "Needs GSTIN" in a second (micro) example if time allows. | "One monthly price, GST shown, setup fee separate or in six instalments. Dependencies are enforced automatically." |
| 1:20–1:35 | Consent | Tick the two required purposes and leave marketing unticked. | "Consent by purpose under the DPDP Act, with retention shown. Images are never stored." |
| 1:35–2:10 | KYC | Enter GSTIN `19EOGXH4115Y1ZL` → **Fetch from DigiLocker** (instant, no photo). Then tap sample **K07**, then **Verify now**. Show the "Legal name doesn't match registry" block. Go back, use **K11**, and show the stale bill and wrong signatory role. Finally use **K02**: verified, including an auto-corrected O/0 and a skewed scan. | "Each document is checked against the registry: checksum, cancelled status, names, addresses, bill age, signatory role. Problems are explained in plain words, and anything we can't fix online goes to a partner." |
| 2:10–2:30 | e-Sign → Tracker | Enter OTP 123456 and pick a slot. On the tracker, tap **Demo: next step** twice and ask *"When will my internet start?"* | "No status calls: the tracker and WhatsApp updates replace them. Questions are answered from the real order status." |
| 2:30–2:55 | Back-office | Show the funnel, the live hand-off from K07 at the top, and the ranked leads with *next best action*. Assign one to a channel partner. | "Leads the advisor couldn't close go to field sales or partners, ranked by a propensity model. Partners earn on assisted journeys, so digital adds to them rather than competing." |
| 2:55–3:00 | — | Show the end card with the URL and repo. | "One plan, one bill, activated in days." |

**Fallbacks while recording:** if Groq is slow, type instead of speaking. The specimen chips (K01–K12) work offline through the local OCR, which takes about 10 s per document on the free tier. Upload them before you start recording.

**Groq free-tier limit:** the vision model allows about 7,000 input tokens a minute, and each document image costs about 2,000 tokens, so roughly 3 documents a minute. Each further photo takes about 20 s while the server waits out the limit. Start KYC with DigiLocker, which needs no vision call, and upload the specimen documents before recording, or a Groq Dev-tier key removes the wait.
