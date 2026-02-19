// ===========================================================================
// file: lib/utils/timestamp_utils.dart
// purpose: Utility functions for timestamp formatting and handling.
//
// Convention: All timestamps stored in the database are UTC.
//   Convert to local time ONLY in the UI layer (these formatting functions).
//   This avoids timezone bugs when users travel or when syncing across devices.
// ===========================================================================

/// Get the current time in UTC.
///
/// Use this instead of DateTime.now() when creating timestamps for storage.
/// DateTime.now() returns local time, which causes problems if the user
/// changes timezone. UTC is unambiguous.
DateTime nowUtc() => DateTime.now().toUtc();

/// Format a DateTime for display in the UI.
///
/// Converts from UTC to local time, then formats as:
///   "Feb 19, 2026 at 10:41 AM"
///
/// The [utcTime] parameter should be a UTC DateTime from the database.
String formatForDisplay(DateTime utcTime) {
  final local = utcTime.toLocal();
  final months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  final month = months[local.month - 1];
  final day = local.day;
  final year = local.year;
  // Convert 24-hour to 12-hour format.
  // Midnight (0) → 12 AM, noon (12) → 12 PM, 1 PM (13) → 1 PM.
  final hour = local.hour > 12
      ? local.hour - 12
      : (local.hour == 0 ? 12 : local.hour);
  final minute = local.minute.toString().padLeft(2, '0');
  final period = local.hour >= 12 ? 'PM' : 'AM';
  return '$month $day, $year at $hour:$minute $period';
}

/// Format a DateTime as a short date string for session cards.
///
/// Shows "Feb 19" for dates in the current year,
/// or "Feb 19, 2025" for dates in a different year.
///
/// The [utcTime] parameter should be a UTC DateTime from the database.
String formatShortDate(DateTime utcTime) {
  final local = utcTime.toLocal();
  final now = DateTime.now();
  final months = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ];
  final month = months[local.month - 1];
  if (local.year == now.year) {
    return '$month ${local.day}';
  }
  return '$month ${local.day}, ${local.year}';
}

/// Format a Duration as a human-readable string.
///
/// Examples:
///   Duration(seconds: 30) → "<1 min"
///   Duration(minutes: 5)  → "5 min"
///   Duration(hours: 1, minutes: 23) → "1 hr 23 min"
///   Duration(hours: 2) → "2 hr"
String formatDuration(Duration duration) {
  if (duration.inMinutes < 1) return '<1 min';
  if (duration.inHours < 1) return '${duration.inMinutes} min';
  final hours = duration.inHours;
  final minutes = duration.inMinutes % 60;
  if (minutes == 0) return '$hours hr';
  return '$hours hr $minutes min';
}
