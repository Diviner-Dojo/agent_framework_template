import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/services/claude_api_service.dart';
import 'package:agentic_journal/services/task_extraction_service.dart';

/// A fake ClaudeApiService that returns canned responses for testing
/// the LLM extraction path. Captures the last prompt for assertion.
class _FakeClaudeApiService extends ClaudeApiService {
  final String response;
  final bool shouldThrow;

  /// The last prompt sent to [chat], for asserting prompt content.
  String? lastPrompt;

  _FakeClaudeApiService(this.response, {this.shouldThrow = false})
    : super(
        environment: const Environment.custom(
          supabaseUrl: 'https://test.supabase.co',
          supabaseAnonKey: 'test-key',
        ),
      );

  @override
  bool get isConfigured => true;

  @override
  Future<String> chat({
    required List<Map<String, String>> messages,
    Map<String, dynamic>? context,
  }) async {
    if (shouldThrow) {
      throw const ClaudeApiException('simulated API error');
    }
    lastPrompt = messages.first['content'];
    return response;
  }
}

void main() {
  // Use a fixed "now" for deterministic tests.
  // Wednesday, February 25, 2026, 10:00 AM local.
  final now = DateTime(2026, 2, 25, 10, 0);

  group('TaskExtractionService — regex fallback (no LLM)', () {
    late TaskExtractionService service;

    setUp(() {
      // No ClaudeApiService → regex fallback.
      service = TaskExtractionService(claudeApi: null);
    });

    group('title extraction', () {
      test('extracts title from "Add a task to buy groceries"', () async {
        final result = await service.extract(
          'Add a task to buy groceries',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), contains('buy groceries'));
      });

      test('extracts title from "Create a to-do for the meeting"', () async {
        final result = await service.extract(
          'Create a to-do for the meeting',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), contains('the meeting'));
      });

      test('handles "New task: finish the report"', () async {
        final result = await service.extract(
          'New task: finish the report',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), contains('finish the report'));
      });

      test('extracts title from "Make a to-do to clean the house"', () async {
        final result = await service.extract(
          'Make a to-do to clean the house',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), contains('clean the house'));
      });

      test('extracts title from "Put a task to email the client"', () async {
        final result = await service.extract(
          'Put a task to email the client',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), contains('email the client'));
      });

      test('capitalizes first letter of extracted title', () async {
        final result = await service.extract(
          'Add a task to buy groceries',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        // First character should be uppercase.
        expect(
          success.task.title[0],
          equals(success.task.title[0].toUpperCase()),
        );
      });

      test('removes "to my task list" from title', () async {
        final result = await service.extract(
          'Add buy milk to my task list',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), isNot(contains('task list')));
        expect(success.task.title.toLowerCase(), contains('buy milk'));
      });

      test('removes "to my to-do list" from title', () async {
        final result = await service.extract(
          'Add call dentist to my to-do list',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), isNot(contains('to-do list')));
        expect(success.task.title.toLowerCase(), contains('call dentist'));
      });
    });

    group('due date extraction', () {
      test('"tomorrow" resolves to next day', () async {
        final result = await service.extract(
          'Add a task to buy groceries tomorrow',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        final expectedDay = now.add(const Duration(days: 1)).day;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.day, expectedDay);
        // Due date should be midnight (start of day).
        expect(success.task.dueDate!.hour, 0);
        expect(success.task.dueDate!.minute, 0);
      });

      test('"today" resolves to current day', () async {
        final result = await service.extract(
          'Add a task to finish the report today',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.day, now.day);
        expect(success.task.dueDate!.month, now.month);
        expect(success.task.dueDate!.year, now.year);
      });

      test('"next Monday" resolves to the following Monday', () async {
        final result = await service.extract(
          'Add a task to prepare slides next Monday',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.weekday, DateTime.monday);
        // Must be after now.
        expect(success.task.dueDate!.isAfter(now), isTrue);
      });

      test('"by Friday" resolves to the coming Friday', () async {
        final result = await service.extract(
          'Create a task to submit report by Friday',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.weekday, DateTime.friday);
      });

      test('"for Saturday" resolves to the coming Saturday', () async {
        final result = await service.extract(
          'New task: clean garage for Saturday',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.weekday, DateTime.saturday);
      });

      test('"due Sunday" resolves to the coming Sunday', () async {
        final result = await service.extract(
          'Add a task to write report due Sunday',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.weekday, DateTime.sunday);
      });

      test('no temporal phrase yields null dueDate', () async {
        final result = await service.extract(
          'Add a task to buy groceries',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNull);
      });

      test('temporal phrase removed from title', () async {
        final result = await service.extract(
          'Add a task to buy groceries tomorrow',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.title.toLowerCase(), isNot(contains('tomorrow')));
      });

      test('"next Wednesday" resolves correctly', () async {
        // now is Wednesday Feb 25, so "next Wednesday" should be March 4.
        final result = await service.extract(
          'Add a task to review code next Wednesday',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.weekday, DateTime.wednesday);
        // Must be strictly after the current Wednesday.
        expect(success.task.dueDate!.isAfter(now), isTrue);
      });
    });

    group('failure cases', () {
      test('returns TaskExtractionFailure for empty message', () async {
        final result = await service.extract('', now);
        expect(result.isSuccess, isFalse);
        final failure = result as TaskExtractionFailure;
        expect(failure.reason, contains('title'));
      });

      test('returns TaskExtractionFailure for unmatchable message', () async {
        // A message that, after removing task-action phrases and temporal refs,
        // leaves nothing extractable.
        final result = await service.extract('add a task', now);
        expect(result.isSuccess, isFalse);
        final failure = result as TaskExtractionFailure;
        expect(failure.reason, contains('title'));
      });

      test(
        'returns TaskExtractionFailure for whitespace-only message',
        () async {
          final result = await service.extract('   ', now);
          expect(result.isSuccess, isFalse);
          expect(result, isA<TaskExtractionFailure>());
        },
      );
    });

    group('regex does not produce notes', () {
      test('regex extraction returns null notes', () async {
        final result = await service.extract(
          'Add a task to buy groceries tomorrow',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.notes, isNull);
      });
    });
  });

  group('TaskExtractionResult sealed types', () {
    test('TaskExtractionSuccess reports isSuccess true', () {
      const success = TaskExtractionSuccess(ExtractedTask(title: 'Test task'));
      expect(success.isSuccess, isTrue);
      expect(success.task.title, 'Test task');
      expect(success.task.dueDate, isNull);
      expect(success.task.notes, isNull);
    });

    test('TaskExtractionFailure reports isSuccess false', () {
      const failure = TaskExtractionFailure('something went wrong');
      expect(failure.isSuccess, isFalse);
      expect(failure.reason, 'something went wrong');
    });

    test('TaskExtractionResult can be pattern-matched via switch', () {
      final TaskExtractionResult result = const TaskExtractionSuccess(
        ExtractedTask(title: 'Groceries'),
      );

      final label = switch (result) {
        TaskExtractionSuccess(task: final t) => 'OK: ${t.title}',
        TaskExtractionFailure(reason: final r) => 'FAIL: $r',
      };
      expect(label, 'OK: Groceries');
    });
  });

  group('ExtractedTask', () {
    test('stores all fields', () {
      final task = ExtractedTask(
        title: 'Write tests',
        dueDate: DateTime.utc(2026, 3, 1),
        notes: 'Use mock API service',
      );
      expect(task.title, 'Write tests');
      expect(task.dueDate, DateTime.utc(2026, 3, 1));
      expect(task.notes, 'Use mock API service');
    });

    test('dueDate defaults to null', () {
      const task = ExtractedTask(title: 'Quick task');
      expect(task.dueDate, isNull);
    });

    test('notes defaults to null', () {
      const task = ExtractedTask(title: 'Quick task');
      expect(task.notes, isNull);
    });
  });

  group('LLM extraction path', () {
    test('parses valid JSON response from LLM', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Buy groceries", "due_date": "2026-03-01T00:00:00Z", '
        '"notes": "Get milk and eggs"}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('add a task to buy groceries', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.title, 'Buy groceries');
      expect(success.task.dueDate, DateTime.utc(2026, 3, 1));
      expect(success.task.notes, 'Get milk and eggs');
    });

    test('strips markdown code fences from LLM response', () async {
      final api = _FakeClaudeApiService(
        '```json\n{"title": "Buy groceries", "due_date": null, '
        '"notes": null}\n```',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.title, 'Buy groceries');
    });

    test('falls back to regex when LLM throws ClaudeApiException', () async {
      final api = _FakeClaudeApiService('', shouldThrow: true);
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract(
        'Add a task to buy groceries tomorrow',
        now,
      );

      // Should still succeed via regex fallback.
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.title.toLowerCase(), contains('buy groceries'));
    });

    test('returns failure for non-object JSON response', () async {
      final api = _FakeClaudeApiService('"just a string"');
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isFalse);
      final failure = result as TaskExtractionFailure;
      expect(failure.reason, contains('not a JSON object'));
    });

    test('returns failure for invalid JSON', () async {
      final api = _FakeClaudeApiService('this is not json at all');
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isFalse);
      final failure = result as TaskExtractionFailure;
      expect(failure.reason, contains('invalid JSON'));
    });

    test('returns failure for missing title', () async {
      final api = _FakeClaudeApiService('{"due_date": "2026-03-01T00:00:00Z"}');
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isFalse);
      final failure = result as TaskExtractionFailure;
      expect(failure.reason, contains('title'));
    });

    test('returns failure for empty title', () async {
      final api = _FakeClaudeApiService(
        '{"title": "", "due_date": null, "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isFalse);
      final failure = result as TaskExtractionFailure;
      expect(failure.reason, contains('title'));
    });

    test('truncates title to 200 characters', () async {
      final longTitle = 'A' * 250;
      final api = _FakeClaudeApiService(
        '{"title": "$longTitle", "due_date": null, "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('long task', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.title.length, 200);
    });

    test('extracts notes from LLM response', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Prepare slides", "due_date": null, '
        '"notes": "Use the new template from design team"}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('prepare slides', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.notes, 'Use the new template from design team');
    });

    test('treats "null" string as no notes', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Quick task", "due_date": null, "notes": "null"}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('quick task', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.notes, isNull);
    });

    test('treats empty notes string as null', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Quick task", "due_date": null, "notes": "   "}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('quick task', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.notes, isNull);
    });

    test('treats "null" string due_date as no due date', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Quick task", "due_date": "null", "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('quick task', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.dueDate, isNull);
    });

    test('ignores due_date in the past beyond 1 day', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Old task", "due_date": "2020-01-01T00:00:00Z", '
        '"notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('old task', now);

      // Should succeed but with null dueDate (out of range).
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.dueDate, isNull);
    });

    test('ignores due_date more than 2 years in the future', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Far future task", "due_date": "2030-01-01T00:00:00Z", '
        '"notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('far future task', now);

      // Should succeed but with null dueDate (out of range).
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.dueDate, isNull);
    });

    test('ignores malformed due_date format gracefully', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Task", "due_date": "not-a-date", "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('task', now);

      // Should succeed but with null dueDate (invalid format).
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.dueDate, isNull);
    });

    test('accepts due_date within valid range', () async {
      // One week from now — well within the 730-day window.
      final nextWeek = now.add(const Duration(days: 7));
      final api = _FakeClaudeApiService(
        '{"title": "Next week task", '
        '"due_date": "${nextWeek.toUtc().toIso8601String()}", '
        '"notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('next week task', now);

      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.dueDate, isNotNull);
    });
  });

  group('context-aware extraction', () {
    test('context included in prompt when provided', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Process the opportunity cube", "due_date": null, '
        '"notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      await service.extract(
        'Add it to my task list',
        now,
        context: [
          {'role': 'user', 'content': 'I need to process the opportunity cube'},
          {'role': 'assistant', 'content': 'That sounds important!'},
        ],
      );

      // The prompt should contain the conversation history block.
      expect(api.lastPrompt, contains('Conversation history:'));
      expect(api.lastPrompt, contains('opportunity cube'));
    });

    test(
      'pronoun "it" in task message resolves to prior context topic',
      () async {
        // Fake API returns a resolved title using conversation context.
        final api = _FakeClaudeApiService(
          '{"title": "Process the opportunity cube", "due_date": null, '
          '"notes": null}',
        );
        final service = TaskExtractionService(claudeApi: api);
        final result = await service.extract(
          'add it to my task list',
          now,
          context: [
            {
              'role': 'user',
              'content': 'I need to process the opportunity cube',
            },
          ],
        );

        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        // LLM used context to resolve "it" — title is meaningful.
        expect(
          success.task.title.toLowerCase(),
          isNot(equals('add it to my task list')),
          reason: 'title should not literally repeat the instruction',
        );
        expect(
          success.task.title.toLowerCase(),
          contains('opportunity cube'),
          reason: 'LLM resolved "it" from conversation context',
        );
      },
    );

    test('no conversation history block when context is null', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Buy milk", "due_date": null, "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      await service.extract('add a task to buy milk', now);

      // No history block when context is null.
      expect(api.lastPrompt, isNot(contains('Conversation history:')));
    });

    test('no conversation history block when context is empty list', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Buy milk", "due_date": null, "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      await service.extract('add a task to buy milk', now, context: []);

      expect(api.lastPrompt, isNot(contains('Conversation history:')));
    });

    test('context role labels are uppercased in prompt', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Call dentist", "due_date": null, "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      await service.extract(
        'remind me to call',
        now,
        context: [
          {'role': 'user', 'content': 'I should call the dentist'},
        ],
      );

      // Role labels should be uppercased: [USER]: ...
      expect(api.lastPrompt, contains('[USER]:'));
    });
  });

  group('LLM extraction — timezone parameter', () {
    test('includes provided IANA timezone in prompt', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Meeting", "due_date": "2026-03-01T00:00:00Z", '
        '"notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      await service.extract(
        'add task for meeting',
        now,
        timezone: 'America/Chicago',
      );

      expect(api.lastPrompt, contains('America/Chicago'));
    });

    test('uses fallback timezone when none provided', () async {
      final api = _FakeClaudeApiService(
        '{"title": "Meeting", "due_date": null, "notes": null}',
      );
      final service = TaskExtractionService(claudeApi: api);
      await service.extract('add task for meeting', now);

      // Should contain some timezone string (device default or UTC).
      expect(api.lastPrompt, isNotNull);
      expect(api.lastPrompt!.contains('timezone:'), isTrue);
    });
  });

  group('LLM extraction — malformed JSON fallback', () {
    test('malformed LLM JSON returns TaskExtractionFailure', () async {
      final api = _FakeClaudeApiService('{broken json!!!');
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isFalse);
      final failure = result as TaskExtractionFailure;
      expect(failure.reason, contains('invalid JSON'));
    });

    test('LLM returns JSON array instead of object', () async {
      final api = _FakeClaudeApiService('[1, 2, 3]');
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isFalse);
      final failure = result as TaskExtractionFailure;
      expect(failure.reason, contains('not a JSON object'));
    });

    test('LLM returns number instead of object', () async {
      final api = _FakeClaudeApiService('42');
      final service = TaskExtractionService(claudeApi: api);
      final result = await service.extract('buy groceries', now);

      expect(result.isSuccess, isFalse);
      final failure = result as TaskExtractionFailure;
      expect(failure.reason, contains('not a JSON object'));
    });
  });

  group('edge cases', () {
    test('case insensitive task action phrases', () async {
      final service = TaskExtractionService(claudeApi: null);
      final result = await service.extract('ADD A TASK TO BUY GROCERIES', now);
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.title.toLowerCase(), contains('buy groceries'));
    });

    test('mixed case temporal phrases', () async {
      final service = TaskExtractionService(claudeApi: null);
      final result = await service.extract(
        'Add a task to clean house TOMORROW',
        now,
      );
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.dueDate, isNotNull);
      expect(success.task.dueDate!.day, now.add(const Duration(days: 1)).day);
    });

    test('message with only temporal phrase and action verb fails', () async {
      final service = TaskExtractionService(claudeApi: null);
      final result = await service.extract('add a task tomorrow', now);
      // After removing "add a task" and "tomorrow", nothing is left.
      expect(result.isSuccess, isFalse);
      expect(result, isA<TaskExtractionFailure>());
    });

    test(
      '"next" weekday that is same as current weekday advances 7 days',
      () async {
        // now is Wednesday Feb 25, 2026.
        final service = TaskExtractionService(claudeApi: null);
        final result = await service.extract(
          'Add a task to review PRs next Wednesday',
          now,
        );
        expect(result.isSuccess, isTrue);
        final success = result as TaskExtractionSuccess;
        expect(success.task.dueDate, isNotNull);
        expect(success.task.dueDate!.weekday, DateTime.wednesday);
        // Should be 7 days from Wednesday Feb 25 = March 4.
        expect(success.task.dueDate!.day, 4);
        expect(success.task.dueDate!.month, 3);
      },
    );

    test('service created with null claudeApi uses regex path', () async {
      final service = TaskExtractionService(claudeApi: null);
      final result = await service.extract(
        'Create a task to review the pull request',
        now,
      );
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      // Regex path does not produce notes.
      expect(success.task.notes, isNull);
    });

    test('title with leading/trailing punctuation is cleaned', () async {
      final service = TaskExtractionService(claudeApi: null);
      // After removing "add a task to", we get ", buy milk ." which should be
      // cleaned of leading/trailing punctuation.
      final result = await service.extract('Add a task to, buy milk.', now);
      expect(result.isSuccess, isTrue);
      final success = result as TaskExtractionSuccess;
      expect(success.task.title, isNot(startsWith(',')));
      expect(success.task.title, isNot(endsWith('.')));
    });
  });
}
