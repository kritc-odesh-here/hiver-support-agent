# SpotifyCares Customer Support Intent Taxonomy

Derived empirically from **43,092** customer interactions replied to by `@SpotifyCares` in the Twitter Customer Support dataset (`twcs.csv`).

## 1. Taxonomy Structure & Distribution Overview

| Category | Category Type | Corpus Frequency | Percentage | Primary Action | Default Escalation Policy |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `ambiguous_vague` | Edge Class | 23,176 | 53.78% | `CLARIFICATION_PROMPT` | `N/A` |
| `subscription_and_billing` | Support Intent | 5,210 | 12.09% | `INFO_PROVISION` | `N/A` |
| `multi_intent` | Edge Class | 3,061 | 7.1% | `DIRECT_TROUBLESHOOT` | `N/A` |
| `music_catalog_and_content` | Support Intent | 3,030 | 7.03% | `INFO_PROVISION` | `N/A` |
| `playlist_library_and_curation` | Support Intent | 2,438 | 5.66% | `DIRECT_TROUBLESHOOT` | `N/A` |
| `account_access_and_login` | Support Intent | 2,106 | 4.89% | `INFO_PROVISION` | `N/A` |
| `non_support_or_chatter` | Edge Class | 1,245 | 2.89% | `INFO_PROVISION` | `N/A` |
| `playback_and_audio` | Support Intent | 1,044 | 2.42% | `DIRECT_TROUBLESHOOT` | `N/A` |
| `offline_listening_and_downloads` | Support Intent | 832 | 1.93% | `DIRECT_TROUBLESHOOT` | `N/A` |
| `unclassifiable_or_foreign` | Edge Class | 459 | 1.07% | `INFO_PROVISION` | `N/A` |
| `service_outage_and_status` | Support Intent | 284 | 0.66% | `INFO_PROVISION` | `N/A` |
| `app_crash_and_performance` | Support Intent | 207 | 0.48% | `DIRECT_TROUBLESHOOT` | `N/A` |

## 2. Intent Definitions, Inclusion & Exclusion Rules

### Intent: `subscription_and_billing`

**Definition**: Customer has questions or problems regarding Premium status, charges, invoices, payment methods, family/student discount verification, or refunds.

**Inclusion Criteria**:
- Queries about unexpected charges, double billing, receipt inquiries
- Premium features inactive despite paying for subscription
- Student verification (SheerID) or Family Plan invite problems
- Payment method declines (PayPal, Credit Card, Prepaid card)
- Subscription cancellation or refund inquiries

**Exclusion Criteria**:
- Inability to log into the account (classify under `account_access_and_login`)
- Song streaming playback glitches (classify under `playback_and_audio`)

**Action & Escalation Policy**: DIRECT_TROUBLESHOOT / INFO_PROVISION for general policy; ESCALATE_TO_HUMAN_DM when checking private receipts, credit cards, or executing refunds.

---

### Intent: `music_catalog_and_content`

**Definition**: Customer is looking for a missing song/album/artist, reporting greyed-out tracks, inquiring about release dates, or asking about explicit lyric filters.

**Inclusion Criteria**:
- Songs or albums missing from artist discography or greyed out
- Track availability differences between countries/regions
- Explicit vs clean album versions or explicit filtering toggles
- Inquiries regarding when new music or podcasts will be uploaded

**Exclusion Criteria**:
- Personal saved tracks missing from a custom playlist (classify under `playlist_library_and_curation`)
- Downloaded offline songs unplayable without internet (classify under `offline_listening_and_downloads`)

**Action & Escalation Policy**: AUTO-HANDLE: Explain regional licensing rights, explicit filter toggles, or direct to Spotify artist content request.

---

### Intent: `playlist_library_and_curation`

**Definition**: Customer experiences issues managing playlists, saved tracks in 'Your Library', shuffle algorithm behavior, queue order, or local file synchronization.

**Inclusion Criteria**:
- Playlists disappeared or empty after updating
- Shuffle repeating the same 5 tracks or not randomizing
- Queue order behaving abnormally or skipping queued tracks
- Local audio files on computer not syncing to mobile app

**Exclusion Criteria**:
- Songs completely unavailable across all of Spotify (classify under `music_catalog_and_content`)
- Tracks failing to download for offline playback (classify under `offline_listening_and_downloads`)

**Action & Escalation Policy**: DIRECT_TROUBLESHOOT: Explain shuffle cache behavior, guide web playlist recovery tool, or check desktop local file sharing settings.

---

### Intent: `account_access_and_login`

**Definition**: Customer cannot access their account due to forgotten credentials, password reset email failures, unexpected logouts, or suspecting account takeover.

**Inclusion Criteria**:
- Login errors ('username or password incorrect')
- Password reset email not arriving in inbox/spam
- Unexpected logouts across devices
- Suspected unauthorized account access or compromised account
- Facebook account login link disconnection issues

**Exclusion Criteria**:
- Payment failure on an active logged-in account (classify under `subscription_and_billing`)

**Action & Escalation Policy**: INFO_PROVISION for standard password reset link; ESCALATE_TO_HUMAN_DM if reset email does not arrive or account is compromised.

---

### Intent: `playback_and_audio`

**Definition**: Customer experiences active playback disruptions including songs skipping, stopping midway, buffering, Bluetooth disconnects, volume issues, or sound distortion.

**Inclusion Criteria**:
- Song suddenly pauses after 10-30 seconds
- Playback skipping tracks rapidly on its own
- Bluetooth speaker or car audio stuttering/disconnecting
- Volume too quiet or audio distorted/scratchy
- Spotify Connect playback transfer fails between devices

**Exclusion Criteria**:
- App crashing completely or closing to homescreen (classify under `app_crash_and_performance`)
- Playback fails specifically when device is offline without wifi (classify under `offline_listening_and_downloads`)

**Action & Escalation Policy**: DIRECT_TROUBLESHOOT: Diagnostic isolation (Bluetooth distance, hard device restart, audio streaming quality settings).

---

### Intent: `offline_listening_and_downloads`

**Definition**: Customer reports that downloaded songs will not play when offline, downloads constantly fail/re-download, or offline songs disappear.

**Inclusion Criteria**:
- Downloaded tracks require internet connection to start
- Green download indicator missing or tracks stuck in 'waiting to download'
- Downloaded playlists removed after clearing storage or switching devices
- Storage capacity or SD card download destination errors

**Exclusion Criteria**:
- General song skipping while connected to high-speed WiFi (classify under `playback_and_audio`)
- App freezing or crashing during launch (classify under `app_crash_and_performance`)

**Action & Escalation Policy**: DIRECT_TROUBLESHOOT: Verify Offline Mode toggle, check 3-device download limit, verify 30-day online check-in requirement.

---

### Intent: `service_outage_and_status`

**Definition**: Customer inquires whether Spotify servers are down, reports platform-wide error messages (500, 502, 'Something went wrong'), or general connectivity failure.

**Inclusion Criteria**:
- Widespread connection errors affecting all tracks and search
- Inquiries like 'is Spotify down for anyone else?'
- Server error pages or status downtime acknowledged by Spotify

**Exclusion Criteria**:
- Single device connection issue while other household devices work fine (classify under `playback_and_audio` or `app_crash_and_performance`)

**Action & Escalation Policy**: INFO_PROVISION: Acknowledge ongoing incident or confirm servers are operational; check @SpotifyStatus.

---

### Intent: `app_crash_and_performance`

**Definition**: App crashes immediately upon launch, freezes on specific screens, displays black/blank screens, suffers extreme lag, or causes severe battery drain.

**Inclusion Criteria**:
- App force-closes or closes automatically upon opening
- Black/blank screen with unresponsive UI
- Extreme lag, unresponsiveness, or app freezing during navigation
- High battery drain or overheating while running in background

**Exclusion Criteria**:
- Audio stops playing while app UI remains responsive (classify under `playback_and_audio`)

**Action & Escalation Policy**: DIRECT_TROUBLESHOOT: Provide clean reinstallation sequence, clear app cache, check OS version compatibility.

---

### Intent: `ambiguous_vague`

**Definition**: Customer expresses frustration or states that Spotify is broken, but provides zero diagnostic context (e.g. 'fix your app', 'why is Spotify not working').

**Inclusion Criteria**:
- One-liner complaints with no symptoms or details
- Vague cries for help without describing what failed

**Exclusion Criteria**:
- Any message mentioning a specific symptom like skipping, crashing, login, or billing

**Action & Escalation Policy**: CLARIFICATION_PROMPT: Inquire what device, OS, and exact behavior the user is experiencing.

---

### Intent: `multi_intent`

**Definition**: Customer message bundles two or more distinct functional complaints together.

**Inclusion Criteria**:
- Message reports both app crash AND billing failure
- Message asks about a missing song AND reports bluetooth skipping

**Exclusion Criteria**:
- Single complaint with secondary emotional remark

**Action & Escalation Policy**: DIRECT_TROUBLESHOOT / ESCALATE: Address the primary technical symptom or escalate if one of the sub-intents requires private account lookup.

---

### Intent: `non_support_or_chatter`

**Definition**: Non-support interactions such as user gratitude, social jokes, memes, or notification that they sent a DM.

**Inclusion Criteria**:
- 'Thanks for the help, sorted now!'
- 'Sent you a DM @SpotifyCares'
- Social commentary or bantering

**Exclusion Criteria**:
- Any message containing an unresolved support inquiry

**Action & Escalation Policy**: INFO_PROVISION: Polite closing acknowledgment; no escalation.

---

### Intent: `unclassifiable_or_foreign`

**Definition**: Messages written in non-English languages, media-only tweets without explanatory text, or garbled text.

**Inclusion Criteria**:
- Non-English queries (e.g. Thai, Spanish, French)
- Tweet consisting solely of a link or screenshot with no text

**Exclusion Criteria**:
- English messages with minor typos

**Action & Escalation Policy**: INFO_PROVISION: Inform customer that Twitter support operates in English and direct to email support.

---

## 3. Ambiguity & Boundary Confusion Analysis

### Boundary 1: `playback_and_audio` vs `app_crash_and_performance`
- **The Confusion**: A user says *'Spotify stops every 2 minutes'*. Is the audio stopping, or is the application crashing?
- **Resolution Rule**: If the message mentions *'closing', 'shutting down', 'force close', or 'black screen'*, classify as `app_crash_and_performance`. If the app stays open but music pauses, cuts out, or skips, classify as `playback_and_audio`.

### Boundary 2: `playback_and_audio` vs `offline_listening_and_downloads`
- **The Confusion**: User says *'My songs won't play on the subway'*. Is it playback or offline storage?
- **Resolution Rule**: If the failure occurs specifically in offline conditions or mentions downloaded tracks, classify as `offline_listening_and_downloads`.

### Boundary 3: `subscription_and_billing` vs `account_access_and_login`
- **The Confusion**: User says *'My Premium is gone, it says Free account'*. Is it billing or login?
- **Resolution Rule**: In Spotify, users frequently accidentally create a second account via Facebook or Apple ID with Free status. If the user states they paid but see Free, classify as `subscription_and_billing` (requires receipt check). If they cannot sign into the account at all, classify as `account_access_and_login`.

### Boundary 4: `music_catalog_and_content` vs `playlist_library_and_curation`
- **The Confusion**: User says *'My favourite songs disappeared'*. Is it licensing removal or user library corruption?
- **Resolution Rule**: If a user mentions their custom playlist or saved library, classify as `playlist_library_and_curation`. If they mention a specific artist's album being greyed out globally, classify as `music_catalog_and_content`.
