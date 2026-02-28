# Manual Test Plan: Agentic Journal

## Context
This test plan covers all user-facing features for manual testing on an Android phone. It's organized by feature area with specific steps and expected results. Tests are ordered so you can work through them sequentially in a single session, building on previous state.

## Prerequisites
- Fresh install of the app (or clear app data for clean state)
- WiFi connection available (some tests require toggling airplane mode)
- Google account available for Calendar and Sync tests
- Supabase backend configured and running

---

## 1. First Launch & Onboarding

| # | Step | Expected Result |
|---|------|-----------------|
| 1.1 | Install and open the app for the first time | Splash screen shows "Setting up your journal...", then navigates to a journal session |
| 1.2 | Observe the session screen | Title says "Journal Entry", an assistant greeting message appears |
| 1.3 | Respond to the onboarding prompts (2-3 messages) | AI asks about journaling preferences, voice/text choice |
| 1.4 | Let the session end naturally or tap "Done" | Summary appears, then you return to the home screen (Session List) |
| 1.5 | Force-close and reopen the app | Home screen loads directly (no onboarding repeat) |

---

## 2. Home Screen (Session List)

| # | Step | Expected Result |
|---|------|-----------------|
| 2.1 | Observe the home screen after onboarding | One session card visible with date, summary, and message count |
| 2.2 | Check app bar | Only the settings gear icon is visible (no search or gallery icons yet) |
| 2.3 | Tap the session card | Navigates to Session Detail screen |
| 2.4 | Press back to return to home | Returns to session list |

---

## 3. Text Journaling (Core Flow)

| # | Step | Expected Result |
|---|------|-----------------|
| 3.1 | Tap the "+" FAB | Spinner appears briefly, then navigates to a new journal session |
| 3.2 | Observe the greeting | Assistant message appears (left-aligned bubble). Title subtitle shows active AI layer (e.g., "Claude" or "Offline") |
| 3.3 | Type a message in the text field and tap Send | Your message appears as a right-aligned bubble. Send button shows loading, then an assistant follow-up appears |
| 3.4 | Send 2-3 more messages | Each gets a follow-up response. Thinking indicator (dots) shows while waiting |
| 3.5 | Tap "Done" in the app bar | Session ends with a closing summary message. "Done" button appears |
| 3.6 | Tap "Done" again to dismiss | Returns to home screen. New session card appears with summary text |
| 3.7 | Verify session card details | Shows date, duration, message count, summary preview |

---

## 4. Session Detail & Resume

| # | Step | Expected Result |
|---|------|-----------------|
| 4.1 | Tap the session card from test 3 | Session Detail screen opens with summary header (italic) and full message transcript |
| 4.2 | Scroll through messages | All user and assistant messages visible as chat bubbles |
| 4.3 | Observe "Continue Entry" button | Button visible in the app bar |
| 4.4 | Tap "Continue Entry" | Spinner, then navigates to active journal session with a resume greeting |
| 4.5 | Send one more message | Follow-up works normally |
| 4.6 | Tap "Done" to end | Summary updates. Return to home screen |

---

## 5. Session Discard

| # | Step | Expected Result |
|---|------|-----------------|
| 5.1 | Start a new session (tap "+") | New session opens with greeting |
| 5.2 | Tap the overflow menu (3-dot) in the app bar | "Discard" option appears (red icon) |
| 5.3 | Tap "Discard" | Confirmation dialog appears |
| 5.4 | Tap "Cancel" | Dialog dismisses, session continues |
| 5.5 | Tap overflow > "Discard" > confirm | Session is deleted, returns to home screen. Session does NOT appear in list |

---

## 6. Empty Session Auto-Discard

| # | Step | Expected Result |
|---|------|-----------------|
| 6.1 | Start a new session (tap "+") | Greeting appears |
| 6.2 | Without typing anything, tap the back arrow | Session auto-closes. SnackBar appears briefly indicating the empty session was discarded |
| 6.3 | Check home screen | No new session card for the empty session |

---

## 7. Session Delete (from List)

| # | Step | Expected Result |
|---|------|-----------------|
| 7.1 | Find a session card on the home screen | Session card visible |
| 7.2 | Tap the overflow menu (3-dot) on the session card | "Delete" option appears |
| 7.3 | Tap "Delete" | Confirmation dialog shows date, summary preview, "This cannot be undone" |
| 7.4 | Tap "Delete" to confirm | Session removed from list |

---

## 8. Voice Mode Setup

| # | Step | Expected Result |
|---|------|-----------------|
| 8.1 | Go to Settings (gear icon) | Settings screen with multiple cards |
| 8.2 | Find the "Voice" card and toggle "Enable voice mode" ON | Sub-settings appear: auto-save, TTS engine dropdown, STT engine dropdown |
| 8.3 | Set TTS engine to "Basic (Offline)" | Speed slider appears (0.5x-1.5x) |
| 8.4 | Set TTS engine to "Natural (ElevenLabs)" | Speed slider disappears |
| 8.5 | Set STT engine to "Offline (71MB model)" | Model status shows "Not downloaded" with info text |
| 8.6 | Set STT engine back to "Google (No download)" | Model status disappears |
| 8.7 | Toggle "Auto-save on exit" | Switch toggles (verify it stays set after leaving and returning to settings) |

---

## 9. Voice Journaling - Push-to-Talk

| # | Step | Expected Result |
|---|------|-----------------|
| 9.1 | With voice mode enabled, start a new session | Session opens. Voice/Text segmented toggle visible at bottom. Mic button visible |
| 9.2 | If prompted, grant microphone permission | Permission dialog appears, grant access |
| 9.3 | Long-press the mic button and speak a sentence | "Listening..." indicator with red dot appears. Real-time transcript preview shows your words |
| 9.4 | Release the mic button | Brief delay (~800ms), then your transcribed message appears as a user bubble |
| 9.5 | Wait for assistant response | Thinking indicator, then assistant message appears. TTS speaks the response |
| 9.6 | Tap the interrupt button while TTS is speaking | Speech stops immediately |
| 9.7 | Long-press mic, speak, then double-tap stop | Recording stops immediately (no 800ms delay) |

---

## 10. Voice Journaling - Continuous Mode

| # | Step | Expected Result |
|---|------|-----------------|
| 10.1 | In a voice session, single-tap the mic button | Continuous mode starts. Phase indicator shows "Listening" |
| 10.2 | Speak naturally | Real-time transcript appears. After you pause, your message is sent automatically |
| 10.3 | Wait for response | Phase cycles: Listening -> Processing -> Speaking. Assistant speaks the response via TTS |
| 10.4 | After TTS finishes, observe | Automatically returns to Listening phase (loop continues) |
| 10.5 | Stay silent for ~15 seconds | Re-prompt is spoken ("Still there?" or similar), listening restarts |
| 10.6 | Tap the stop button | Voice loop stops, returns to idle. Mic button reappears |

---

## 11. Voice/Text Toggle

| # | Step | Expected Result |
|---|------|-----------------|
| 11.1 | In an active voice session, tap "Text" on the segmented toggle | Voice stops. Text field and keyboard appear. Mic button becomes send button |
| 11.2 | Type and send a text message | Works normally as text mode |
| 11.3 | Tap "Voice" on the segmented toggle | Returns to voice mode. Mic button reappears |

---

## 12. Photo Capture

| # | Step | Expected Result |
|---|------|-----------------|
| 12.1 | In an active session, tap the camera button | Bottom sheet appears with options: Take Photo, Choose from Gallery, Record Video, Choose Video |
| 12.2 | Tap "Take Photo" | Device camera opens |
| 12.3 | Take a photo and confirm | Photo preview dialog appears in the app |
| 12.4 | Tap confirm on the preview | "Processing photo..." indicator, then photo thumbnail appears in a message bubble |
| 12.5 | Tap the photo thumbnail in chat | Full-screen PhotoViewer opens with hero animation |
| 12.6 | Press back from PhotoViewer | Returns to session |
| 12.7 | Tap camera > "Choose Photo from Gallery" | Device gallery opens. Select a photo -> preview -> confirm -> photo appears in chat |

---

## 13. Video Capture

| # | Step | Expected Result |
|---|------|-----------------|
| 13.1 | In an active session, tap camera > "Record Video" | Video camera opens with 60-second limit |
| 13.2 | Record a short video and confirm | "Processing video..." indicator, then video thumbnail appears with play overlay and duration badge |
| 13.3 | Tap the video thumbnail | Video plays in full-screen player |
| 13.4 | Tap camera > "Choose Video from Gallery" | Gallery opens for video selection. Same flow as above |

---

## 14. Photo Gallery

| # | Step | Expected Result |
|---|------|-----------------|
| 14.1 | Return to home screen (after taking at least 1 photo) | Gallery icon now visible in app bar |
| 14.2 | Tap the gallery icon | Photo Gallery screen opens with 3-column grid |
| 14.3 | Tap a photo | Full-screen PhotoViewer opens |
| 14.4 | Press back | Returns to gallery grid |

---

## 15. Search

| # | Step | Expected Result |
|---|------|-----------------|
| 15.1 | Create sessions until you have 5+ total | Search icon appears in home screen app bar |
| 15.2 | Tap the search icon | Search screen opens with text field and filter chips (Date, Mood, People, Topics) |
| 15.3 | Type a word that appears in your journal entries | Results appear after ~300ms debounce. Each result shows session info |
| 15.4 | Tap the X button in the search field | Field clears, results disappear |
| 15.5 | Tap the "Date" filter chip | Bottom sheet with presets: "Last 7 days", "Last 30 days", "This year", "Custom range..." |
| 15.6 | Select "Last 7 days" | Chip updates to show active filter. Results filter accordingly |
| 15.7 | Tap a Mood/People/Topics chip | Multi-select bottom sheet. Toggle items, tap "Apply" |
| 15.8 | With filters active and no results | Empty state shows "No entries match your filters" with "Clear filters" button |
| 15.9 | Tap a search result | Navigates to Session Detail |

---

## 16. Settings - AI Configuration

| # | Step | Expected Result |
|---|------|-----------------|
| 16.1 | Go to Settings > Conversation AI card | Shows "Prefer Claude when online" switch, "Journal only mode" switch, local AI status |
| 16.2 | Toggle "Journal only mode" ON | Claude switch becomes disabled. Personality section hides |
| 16.3 | Start a new session with journal-only mode on | Greeting appears, but after you send a message, no AI follow-up is generated |
| 16.4 | Toggle "Journal only mode" OFF | Claude switch re-enables. Personality section reappears |
| 16.5 | Change assistant name | Enter a new name, submit. Info text says "Changes take effect on the next session" |
| 16.6 | Change conversation style dropdown | Select different style (Warm/Professional/Curious) |
| 16.7 | Enter a custom prompt (up to 500 chars) | Text area accepts input. Character limit enforced |

---

## 17. Settings - Digital Assistant

| # | Step | Expected Result |
|---|------|-----------------|
| 17.1 | Go to Settings > Digital Assistant card | Shows current status: "Default assistant: Yes" or "Default assistant: No" |
| 17.2 | Tap "Set as Default Assistant" | Opens Android system settings (Default Apps > Digital Assistant) |
| 17.3 | Set the app as default assistant and return | Status updates to "Default assistant: Yes" |
| 17.4 | Long-press the Home button (Android gesture) | App launches and auto-starts a new journal session |
| 17.5 | End the session and try voice assist gesture | App launches with voice mode auto-enabled, continuous mode starts |

---

## 18. Settings - Location

| # | Step | Expected Result |
|---|------|-----------------|
| 18.1 | Go to Settings > Location card | Privacy disclosure text, "Enable location" toggle (off by default) |
| 18.2 | Toggle location ON | Permission dialog appears. Grant permission |
| 18.3 | Start a new session, then view its detail | Location chip with pin icon shows your approximate location |
| 18.4 | Go to Settings > Location > "Clear Location Data" | Confirmation dialog appears. Confirm -> location data removed from all sessions |
| 18.5 | Toggle location ON, deny permission | SnackBar says "Location permission is required" |
| 18.6 | Toggle location ON after permanently denying | SnackBar with "Open Settings" action to go to app permissions |

---

## 19. Calendar Integration

| # | Step | Expected Result |
|---|------|-----------------|
| 19.1 | Go to Settings > Calendar card | Shows "Google Calendar: Not connected" with Connect button |
| 19.2 | Tap "Connect" | Google OAuth flow. Sign in with your Google account |
| 19.3 | After connecting | Status shows "Google Calendar: Connected". Auto-suggest and Require confirmation toggles visible |
| 19.4 | Verify "Require confirmation" is locked ON | Toggle is non-interactive with info text |
| 19.5 | Start a new session and say/type "Schedule a meeting tomorrow at 3pm" | Calendar event card appears: extracting spinner -> event details (title, date, time) |
| 19.6 | If the time is in the past | Orange warning: "This time is in the past" |
| 19.7 | Tap "Add to Calendar" | Event created in Google Calendar. Assistant confirms |
| 19.8 | Tap X to dismiss a different event suggestion | Card disappears, no event created |
| 19.9 | Go to Settings > Calendar > Disconnect | Status reverts to "Not connected" |

---

## 20. Calendar - Deferred Events (Voice Mode)

| # | Step | Expected Result |
|---|------|-----------------|
| 20.1 | Disconnect Google Calendar in Settings | Status shows "Not connected" |
| 20.2 | Start a voice session and mention a calendar event | Voice says event is saved and can be added later when you connect Google Calendar |
| 20.3 | End the session and return to home screen | "Pending calendar events" banner appears at top |
| 20.4 | Tap the banner | Google OAuth flow triggers. After connecting, pending events are batch-created |
| 20.5 | Observe | SnackBar shows success/failure count. Banner disappears |

---

## 21. Cloud Sync (Supabase)

| # | Step | Expected Result |
|---|------|-----------------|
| 21.1 | Go to Settings > Cloud Sync card | Shows "Sign in to sync..." with "Sign In" button |
| 21.2 | Tap "Sign In" | Auth screen opens with email/password fields |
| 21.3 | Toggle to "Create Account" | Form switches to sign-up mode with password validation (6+ chars) |
| 21.4 | Create an account (or sign in) | Returns to Settings. Shows email, pending sync count |
| 21.5 | Tap "Sync Now" | Spinner + "Syncing..." text. After completion, shows "All sessions synced" or updated pending count |
| 21.6 | Check session cards on home screen | Sync status icons update (cloud-done = synced) |
| 21.7 | Tap "Sign Out" | Returns to unauthenticated state |
| 21.8 | Test invalid login | Error message appears in red on the auth screen |
| 21.9 | Tap "Skip" on auth screen | Returns to settings without signing in |

---

## 22. Data Management

| # | Step | Expected Result |
|---|------|-----------------|
| 22.1 | Go to Settings > Data Management card | Shows session count, photo count, and storage size |
| 22.2 | Tap "Clear All Entries" | First confirmation dialog appears |
| 22.3 | Type "DELETE" in the confirmation field | Delete button enables |
| 22.4 | Confirm deletion | All sessions, messages, photos removed. Home screen shows empty state |

---

## 23. Memory Recall

| # | Step | Expected Result |
|---|------|-----------------|
| 23.1 | Create 2-3 sessions about different topics (e.g., one about work, one about a hobby) | Sessions with summaries visible on home screen |
| 23.2 | Start a new session and type "What did I say about [topic]?" | AI searches past entries and responds with a recall message |
| 23.3 | Observe the recall message format | Shows "From your journal" header, citation chips, "Based on your entries" footer |
| 23.4 | If confidence is ambiguous | Inline prompt: "Search my journal?" / "Continue journaling?" |

---

## 24. Offline Behavior

| # | Step | Expected Result |
|---|------|-----------------|
| 24.1 | Enable airplane mode | No connectivity |
| 24.2 | Start a new session | Session starts. Title subtitle shows "Offline" (rule-based layer) |
| 24.3 | Send messages | Rule-based follow-up responses work (simpler than Claude) |
| 24.4 | End session | Summary is rule-based (first sentence of messages) |
| 24.5 | Open Search | Offline banner: "Searching local data - Natural language recall unavailable offline" |
| 24.6 | Search works locally | LIKE-based search still returns results |
| 24.7 | Disable airplane mode | Subsequent sessions can use Claude again |

---

## 25. App Lifecycle

| # | Step | Expected Result |
|---|------|-----------------|
| 25.1 | Start a session with auto-save ON (Settings > Voice > Auto-save) | Active session running |
| 25.2 | Switch to another app (background the journal app) | Session auto-saves and ends |
| 25.3 | Return to the app | Home screen shows the saved session |
| 25.4 | Start a session with auto-save OFF | Active session running |
| 25.5 | Switch to another app and return | Session is still active (not auto-saved) |

---

## 26. Theme & Display

| # | Step | Expected Result |
|---|------|-----------------|
| 26.1 | Set device to light mode | App renders in light theme |
| 26.2 | Set device to dark mode | App renders in dark theme |
| 26.3 | Verify all screens are readable in both themes | No contrast issues, text legible, icons visible |

---

## 27. Edge Cases & Error Recovery

| # | Step | Expected Result |
|---|------|-----------------|
| 27.1 | Deny microphone permission, then try voice mode | Appropriate error handling (permission request or error message) |
| 27.2 | Start a voice session, receive a phone call | Voice pauses. After call ends and you return, voice resumes with "Welcome back" |
| 27.3 | Try to start a second session while one is active | Returns to the existing active session (no duplicate) |
| 27.4 | In voice continuous mode, stay silent for 45+ seconds | After ~15s silence: re-prompt. After 3 timeouts: "Try typing instead" suggestion |
| 27.5 | Type special characters in journal entry (emojis, Unicode) | Characters preserved correctly in display and detail view |
| 27.6 | Very long message (500+ words) | Message sends and displays correctly, chat scrolls |

---

## Verification Checklist

After completing all tests, verify:
- [ ] All sessions created during testing appear in the session list
- [ ] Session details show correct message counts and summaries
- [ ] Photos taken during testing appear in the gallery
- [ ] No crashes or unhandled errors occurred
- [ ] Settings changes persist after closing and reopening the app
