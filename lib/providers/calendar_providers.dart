// ===========================================================================
// file: lib/providers/calendar_providers.dart
// purpose: Riverpod providers for Google Calendar integration.
//
// Follows the pattern of location_providers.dart — providers manage
// service instances, connection state, and user preferences.
//
// See: ADR-0020 (Google Calendar Integration)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/event_extraction_service.dart';
import '../services/google_auth_service.dart';
import '../services/google_calendar_service.dart';
import 'database_provider.dart';
import 'session_providers.dart';

/// Provides the GoogleAuthService singleton.
///
/// Override in tests to inject a fake service with mock callables.
final googleAuthServiceProvider = Provider<GoogleAuthService>((ref) {
  return GoogleAuthService();
});

/// Whether the user is signed in to Google Calendar.
///
/// Starts as false and is updated by [GoogleConnectionNotifier].
/// The UI watches this to show connect/disconnect state in settings
/// and to gate calendar event creation.
final isGoogleConnectedProvider =
    StateNotifierProvider<GoogleConnectionNotifier, bool>((ref) {
      final authService = ref.watch(googleAuthServiceProvider);
      return GoogleConnectionNotifier(authService);
    });

/// Manages the Google connection state.
///
/// Checks for existing sign-in on initialization and provides
/// connect/disconnect methods for the settings UI.
class GoogleConnectionNotifier extends StateNotifier<bool> {
  final GoogleAuthService _authService;

  GoogleConnectionNotifier(this._authService) : super(false) {
    _checkExistingSignIn();
  }

  /// Check if the user was previously signed in (silent restore).
  Future<void> _checkExistingSignIn() async {
    final signedIn = await _authService.isSignedIn();
    if (signedIn) {
      // Try to silently restore the session.
      final account = await _authService.trySilentSignIn();
      state = account != null;
    }
  }

  /// Trigger the Google sign-in consent flow.
  ///
  /// Returns true if sign-in succeeded. Rethrows [GoogleAuthException]
  /// for configuration/network errors so the UI can display them.
  Future<bool> connect() async {
    final account = await _authService.signIn();
    state = account != null;
    return state;
  }

  /// Disconnect from Google (revoke tokens + clear local state).
  Future<void> disconnect() async {
    await _authService.disconnect();
    state = false;
  }
}

/// SharedPreferences key for the calendar auto-suggest toggle.
const _autoSuggestKey = 'calendar_auto_suggest';

/// SharedPreferences key for the calendar confirmation toggle.
const _confirmationKey = 'calendar_require_confirmation';

/// Whether the AI should auto-suggest calendar events from conversation.
///
/// Default: true (on). When off, the intent classifier still runs but
/// calendar/reminder intents are not surfaced to the user.
final calendarAutoSuggestProvider =
    StateNotifierProvider<CalendarAutoSuggestNotifier, bool>((ref) {
      return CalendarAutoSuggestNotifier();
    });

/// Manages the auto-suggest preference.
class CalendarAutoSuggestNotifier extends StateNotifier<bool> {
  CalendarAutoSuggestNotifier() : super(true) {
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_autoSuggestKey) ?? true;
  }

  /// Toggle auto-suggest on/off.
  Future<void> setEnabled(bool value) async {
    state = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_autoSuggestKey, value);
  }
}

/// Whether event creation requires explicit user confirmation.
///
/// Default: true (always confirm). In v1, this cannot be disabled —
/// events are never auto-created (ADR-0020 §8).
final calendarConfirmationProvider =
    StateNotifierProvider<CalendarConfirmationNotifier, bool>((ref) {
      return CalendarConfirmationNotifier();
    });

/// Manages the confirmation preference (always-on in v1).
class CalendarConfirmationNotifier extends StateNotifier<bool> {
  CalendarConfirmationNotifier() : super(true) {
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = prefs.getBool(_confirmationKey) ?? true;
  }

  /// Set confirmation requirement. In v1, this is always true.
  Future<void> setEnabled(bool value) async {
    state = value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_confirmationKey, value);
  }
}

/// Provides the EventExtractionService for parsing calendar details
/// from natural language.
///
/// Injects ClaudeApiService for LLM-powered extraction when available.
/// Falls back to regex extraction when offline.
final eventExtractionServiceProvider = Provider<EventExtractionService>((ref) {
  final claudeApi = ref.watch(claudeApiServiceProvider);
  return EventExtractionService(claudeApi: claudeApi);
});

/// Provides the GoogleCalendarService, or null when not connected.
///
/// Lazily creates the service from the authenticated HTTP client.
/// Returns null when the user is not signed in to Google.
final googleCalendarServiceProvider = Provider<GoogleCalendarService?>((ref) {
  // This provider is manually invalidated after sign-in/sign-out.
  // It cannot watch isGoogleConnectedProvider because it needs
  // synchronous access — the auth client fetch happens at usage time.
  return null;
});

/// Provides the count of pending calendar events (PENDING_CREATE status).
///
/// Used by the session list screen to show a banner when deferred
/// events exist. The provider re-evaluates when the database changes.
final pendingCalendarEventsCountProvider = FutureProvider<int>((ref) async {
  final calendarEventDao = ref.watch(calendarEventDaoProvider);
  final events = await calendarEventDao.getPendingEvents();
  return events.length;
});
