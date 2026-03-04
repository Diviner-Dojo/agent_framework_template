import 'package:flutter_test/flutter_test.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/repositories/sync_repository.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/services/supabase_service.dart';

/// A mock SupabaseService that reports as authenticated but has no real client.
class _FakeAuthenticatedSupabaseService extends SupabaseService {
  _FakeAuthenticatedSupabaseService()
    : super(
        environment: const Environment.custom(
          supabaseUrl: '',
          supabaseAnonKey: '',
        ),
      );

  @override
  bool get isAuthenticated => true;
}

/// A SyncRepository subclass that captures the upload payload for verification.
///
/// Overrides [uploadSession] to record the session data that would be uploaded,
/// enabling assertions on which fields are included in the sync payload.
class _PayloadCaptureSyncRepository extends SyncRepository {
  final List<JournalSession> uploadedSessions = [];

  _PayloadCaptureSyncRepository({
    required super.supabaseService,
    required super.sessionDao,
    required super.messageDao,
  });

  @override
  Future<void> uploadSession(JournalSession session) async {
    uploadedSessions.add(session);
  }
}

void main() {
  late AppDatabase database;
  late SessionDao sessionDao;
  late MessageDao messageDao;

  setUp(() {
    database = AppDatabase.forTesting(NativeDatabase.memory());
    sessionDao = SessionDao(database);
    messageDao = MessageDao(database);
  });

  tearDown(() async {
    await database.close();
  });

  group('Sync payload — weather field boundary (ADR-0034)', () {
    test(
      'weather columns are excluded from buildSessionUpsertMap (stay local)',
      () async {
        // Weather is ambient metadata captured for local journaling context.
        // It is intentionally excluded from cloud sync — see the comment in
        // buildSessionUpsertMap and ADR-0034. This test is the load-bearing
        // assertion that the exclusion is deliberate, not accidental.
        // (Mirrors the coordinate exclusion test in the location group below,
        // per the ADR-0019 §3 precedent.)
        await sessionDao.createSession(
          'weather-session',
          DateTime.utc(2026, 3, 4),
          'America/New_York',
        );
        await sessionDao.updateSessionWeather(
          'weather-session',
          weatherTempC: 14.5,
          weatherCode: 1,
          weatherDescription: 'Mainly clear',
        );

        final session = await sessionDao.getSessionById('weather-session');
        expect(session, isNotNull);

        final map = SyncRepository.buildSessionUpsertMap(session!, 'user-1');

        // Weather columns must NOT appear in the sync payload — local-only.
        expect(
          map.containsKey('weather_temp_c'),
          isFalse,
          reason: 'weather_temp_c must not be synced to cloud (ADR-0034)',
        );
        expect(
          map.containsKey('weather_code'),
          isFalse,
          reason: 'weather_code must not be synced to cloud (ADR-0034)',
        );
        expect(
          map.containsKey('weather_description'),
          isFalse,
          reason: 'weather_description must not be synced to cloud (ADR-0034)',
        );
      },
    );
  });

  group('Sync payload — location field boundary (ADR-0019 §3)', () {
    test(
      'session with location has locationName available for upload',
      () async {
        final repo = _PayloadCaptureSyncRepository(
          supabaseService: _FakeAuthenticatedSupabaseService(),
          sessionDao: sessionDao,
          messageDao: messageDao,
        );

        await sessionDao.createSession(
          'loc-session',
          DateTime.utc(2026, 2, 25),
          'UTC',
        );
        await sessionDao.updateSessionLocation(
          'loc-session',
          latitude: 39.74,
          longitude: -104.99,
          locationAccuracy: 25.0,
          locationName: 'Denver, Colorado',
        );

        await repo.syncPendingSessions();

        expect(repo.uploadedSessions, hasLength(1));
        final uploaded = repo.uploadedSessions.first;
        // locationName IS available on the session object for sync.
        expect(uploaded.locationName, 'Denver, Colorado');
        // Coordinates are also present on the session object (local storage).
        // The SyncRepository.uploadSession() method is responsible for
        // INCLUDING location_name and EXCLUDING lat/lng from the upsert map.
        expect(uploaded.latitude, 39.74);
        expect(uploaded.longitude, -104.99);
      },
    );

    test('session without location has null location fields', () async {
      final repo = _PayloadCaptureSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
      );

      await sessionDao.createSession(
        'no-loc-session',
        DateTime.utc(2026, 2, 25),
        'UTC',
      );

      await repo.syncPendingSessions();

      expect(repo.uploadedSessions, hasLength(1));
      final uploaded = repo.uploadedSessions.first;
      expect(uploaded.locationName, isNull);
      expect(uploaded.latitude, isNull);
      expect(uploaded.longitude, isNull);
    });

    test(
      'upsert map includes location_name but not lat/lng/accuracy (ADR-0019 §3)',
      () async {
        // This is the load-bearing sync boundary test promised by ADR-0019 §3.
        // It calls the real buildSessionUpsertMap() and asserts that raw
        // coordinates are excluded from the cloud payload.

        await sessionDao.createSession(
          'loc-session',
          DateTime.utc(2026, 2, 25),
          'UTC',
        );
        await sessionDao.updateSessionLocation(
          'loc-session',
          latitude: 39.74,
          longitude: -104.99,
          locationAccuracy: 25.0,
          locationName: 'Denver, Colorado',
        );

        final session = await sessionDao.getSessionById('loc-session');
        expect(session, isNotNull);

        // Build the upsert map using the production code path.
        final map = SyncRepository.buildSessionUpsertMap(
          session!,
          'test-user-id',
        );

        // location_name IS included in the cloud payload.
        expect(map.containsKey('location_name'), isTrue);
        expect(map['location_name'], 'Denver, Colorado');

        // Raw coordinates are EXCLUDED — they stay local (ADR-0019 §3).
        expect(
          map.containsKey('latitude'),
          isFalse,
          reason: 'latitude must not be synced to cloud',
        );
        expect(
          map.containsKey('longitude'),
          isFalse,
          reason: 'longitude must not be synced to cloud',
        );
        expect(
          map.containsKey('location_accuracy'),
          isFalse,
          reason: 'location_accuracy must not be synced to cloud',
        );
      },
    );

    test('cleared location data syncs as null locationName', () async {
      final repo = _PayloadCaptureSyncRepository(
        supabaseService: _FakeAuthenticatedSupabaseService(),
        sessionDao: sessionDao,
        messageDao: messageDao,
      );

      await sessionDao.createSession(
        'cleared-session',
        DateTime.utc(2026, 2, 25),
        'UTC',
      );
      await sessionDao.updateSessionLocation(
        'cleared-session',
        latitude: 39.74,
        longitude: -104.99,
        locationName: 'Denver, Colorado',
      );

      // Sync once with location.
      await repo.syncPendingSessions();
      expect(repo.uploadedSessions.first.locationName, 'Denver, Colorado');

      // Clear all location data.
      await sessionDao.clearAllLocationData();

      // Sync again — locationName should now be null.
      repo.uploadedSessions.clear();
      await repo.syncPendingSessions();

      expect(repo.uploadedSessions, hasLength(1));
      expect(repo.uploadedSessions.first.locationName, isNull);
      expect(repo.uploadedSessions.first.latitude, isNull);
    });
  });
}
