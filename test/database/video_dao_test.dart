import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/video_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';

void main() {
  late AppDatabase db;
  late VideoDao videoDao;
  late SessionDao sessionDao;

  setUp(() {
    db = AppDatabase.forTesting(NativeDatabase.memory());
    videoDao = VideoDao(db);
    sessionDao = SessionDao(db);
  });

  tearDown(() async {
    await db.close();
  });

  /// Create a test session and return its ID.
  Future<String> createSession(String sessionId) async {
    await sessionDao.createSession(sessionId, DateTime.utc(2026, 2, 25), 'UTC');
    return sessionId;
  }

  group('VideoDao', () {
    group('insertVideo', () {
      test('inserts a video record successfully', () async {
        await createSession('s1');

        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 30,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        final video = await videoDao.getVideoById('v1');
        expect(video, isNotNull);
        expect(video!.videoId, 'v1');
        expect(video.sessionId, 's1');
        expect(video.localPath, 'videos/s1/v1.mp4');
        expect(video.thumbnailPath, 'videos/s1/v1_thumb.jpg');
        expect(video.durationSeconds, 30);
        expect(video.syncStatus, 'PENDING');
      });

      test('inserts video with all optional fields', () async {
        await createSession('s1');

        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 45,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
          messageId: 'm1',
          description: 'Morning walk',
          width: 1920,
          height: 1080,
          fileSizeBytes: 52428800,
        );

        final video = await videoDao.getVideoById('v1');
        expect(video!.messageId, 'm1');
        expect(video.description, 'Morning walk');
        expect(video.width, 1920);
        expect(video.height, 1080);
        expect(video.fileSizeBytes, 52428800);
      });
    });

    group('getVideoById', () {
      test('returns null for non-existent video', () async {
        final video = await videoDao.getVideoById('nonexistent');
        expect(video, isNull);
      });
    });

    group('getVideosForSession', () {
      test('returns videos ordered by timestamp ascending', () async {
        await createSession('s1');

        await videoDao.insertVideo(
          videoId: 'v2',
          sessionId: 's1',
          localPath: 'videos/s1/v2.mp4',
          thumbnailPath: 'videos/s1/v2_thumb.jpg',
          durationSeconds: 20,
          timestamp: DateTime.utc(2026, 2, 25, 10, 30),
        );
        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        final videos = await videoDao.getVideosForSession('s1');
        expect(videos.length, 2);
        expect(videos[0].videoId, 'v1'); // Earlier timestamp first.
        expect(videos[1].videoId, 'v2');
      });

      test('returns empty list for session with no videos', () async {
        await createSession('s1');
        final videos = await videoDao.getVideosForSession('s1');
        expect(videos, isEmpty);
      });

      test('does not return videos from other sessions', () async {
        await createSession('s1');
        await createSession('s2');

        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        final videos = await videoDao.getVideosForSession('s2');
        expect(videos, isEmpty);
      });
    });

    group('watchVideosForSession', () {
      test('emits videos as a stream', () async {
        await createSession('s1');

        final stream = videoDao.watchVideosForSession('s1');

        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        await expectLater(
          stream,
          emitsThrough(
            predicate<List<Video>>(
              (videos) => videos.length == 1 && videos[0].videoId == 'v1',
            ),
          ),
        );
      });
    });

    group('updateCloudUrl', () {
      test('sets cloud URL and updated_at', () async {
        await createSession('s1');
        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        await videoDao.updateCloudUrl(
          'v1',
          'https://storage.example.com/v1.mp4',
        );

        final video = await videoDao.getVideoById('v1');
        expect(video!.cloudUrl, 'https://storage.example.com/v1.mp4');
      });
    });

    group('updateSyncStatus', () {
      test('updates sync status', () async {
        await createSession('s1');
        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        await videoDao.updateSyncStatus('v1', 'SYNCED');

        final video = await videoDao.getVideoById('v1');
        expect(video!.syncStatus, 'SYNCED');
      });
    });

    group('getVideosToSync', () {
      test('returns PENDING and FAILED videos', () async {
        await createSession('s1');

        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );
        await videoDao.insertVideo(
          videoId: 'v2',
          sessionId: 's1',
          localPath: 'videos/s1/v2.mp4',
          thumbnailPath: 'videos/s1/v2_thumb.jpg',
          durationSeconds: 20,
          timestamp: DateTime.utc(2026, 2, 25, 10, 30),
        );
        await videoDao.insertVideo(
          videoId: 'v3',
          sessionId: 's1',
          localPath: 'videos/s1/v3.mp4',
          thumbnailPath: 'videos/s1/v3_thumb.jpg',
          durationSeconds: 15,
          timestamp: DateTime.utc(2026, 2, 25, 11, 0),
        );

        // v2 synced, v3 failed.
        await videoDao.updateSyncStatus('v2', 'SYNCED');
        await videoDao.updateSyncStatus('v3', 'FAILED');

        final toSync = await videoDao.getVideosToSync();
        expect(toSync.length, 2); // v1 (PENDING) + v3 (FAILED)
        final ids = toSync.map((v) => v.videoId).toSet();
        expect(ids, containsAll(['v1', 'v3']));
      });
    });

    group('deleteVideo', () {
      test('deletes a single video', () async {
        await createSession('s1');
        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        final deleted = await videoDao.deleteVideo('v1');
        expect(deleted, 1);

        final video = await videoDao.getVideoById('v1');
        expect(video, isNull);
      });

      test('returns 0 when video does not exist', () async {
        final deleted = await videoDao.deleteVideo('nonexistent');
        expect(deleted, 0);
      });
    });

    group('deleteVideosBySession', () {
      test('deletes all videos for a session', () async {
        await createSession('s1');
        await createSession('s2');

        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );
        await videoDao.insertVideo(
          videoId: 'v2',
          sessionId: 's1',
          localPath: 'videos/s1/v2.mp4',
          thumbnailPath: 'videos/s1/v2_thumb.jpg',
          durationSeconds: 20,
          timestamp: DateTime.utc(2026, 2, 25, 10, 30),
        );
        await videoDao.insertVideo(
          videoId: 'v3',
          sessionId: 's2',
          localPath: 'videos/s2/v3.mp4',
          thumbnailPath: 'videos/s2/v3_thumb.jpg',
          durationSeconds: 15,
          timestamp: DateTime.utc(2026, 2, 25, 11, 0),
        );

        final deleted = await videoDao.deleteVideosBySession('s1');
        expect(deleted, 2);

        // s2's video should still exist.
        final remaining = await videoDao.getVideosForSession('s2');
        expect(remaining.length, 1);
      });
    });

    group('getVideoCount', () {
      test('returns 0 when no videos exist', () async {
        final count = await videoDao.getVideoCount();
        expect(count, 0);
      });

      test('returns correct count', () async {
        await createSession('s1');
        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );
        await videoDao.insertVideo(
          videoId: 'v2',
          sessionId: 's1',
          localPath: 'videos/s1/v2.mp4',
          thumbnailPath: 'videos/s1/v2_thumb.jpg',
          durationSeconds: 20,
          timestamp: DateTime.utc(2026, 2, 25, 10, 30),
        );

        final count = await videoDao.getVideoCount();
        expect(count, 2);
      });
    });

    group('getTotalVideoSize', () {
      test('returns 0 when no videos exist', () async {
        final size = await videoDao.getTotalVideoSize();
        expect(size, 0);
      });

      test('returns 0 when all fileSizeBytes are null', () async {
        await createSession('s1');
        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );

        final size = await videoDao.getTotalVideoSize();
        expect(size, 0);
      });

      test('sums file sizes correctly', () async {
        await createSession('s1');
        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
          fileSizeBytes: 50000000,
        );
        await videoDao.insertVideo(
          videoId: 'v2',
          sessionId: 's1',
          localPath: 'videos/s1/v2.mp4',
          thumbnailPath: 'videos/s1/v2_thumb.jpg',
          durationSeconds: 20,
          timestamp: DateTime.utc(2026, 2, 25, 10, 30),
          fileSizeBytes: 30000000,
        );

        final size = await videoDao.getTotalVideoSize();
        expect(size, 80000000);
      });
    });

    group('deleteAllVideos', () {
      test('deletes all videos across sessions', () async {
        await createSession('s1');
        await createSession('s2');

        await videoDao.insertVideo(
          videoId: 'v1',
          sessionId: 's1',
          localPath: 'videos/s1/v1.mp4',
          thumbnailPath: 'videos/s1/v1_thumb.jpg',
          durationSeconds: 10,
          timestamp: DateTime.utc(2026, 2, 25, 10, 0),
        );
        await videoDao.insertVideo(
          videoId: 'v2',
          sessionId: 's2',
          localPath: 'videos/s2/v2.mp4',
          thumbnailPath: 'videos/s2/v2_thumb.jpg',
          durationSeconds: 20,
          timestamp: DateTime.utc(2026, 2, 25, 10, 30),
        );

        final deleted = await videoDao.deleteAllVideos();
        expect(deleted, 2);

        final count = await videoDao.getVideoCount();
        expect(count, 0);
      });
    });
  });
}
