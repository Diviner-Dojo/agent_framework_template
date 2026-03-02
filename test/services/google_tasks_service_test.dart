import 'package:flutter_test/flutter_test.dart';
import 'package:googleapis/tasks/v1.dart' as gtasks;
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/services/google_tasks_service.dart';

@GenerateNiceMocks([
  MockSpec<gtasks.TasksApi>(),
  MockSpec<gtasks.TasklistsResource>(),
  MockSpec<gtasks.TasksResource>(),
])
import 'google_tasks_service_test.mocks.dart';

void main() {
  late MockTasksApi mockApi;
  late MockTasklistsResource mockTasklists;
  late MockTasksResource mockTasks;
  late GoogleTasksService service;

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    mockApi = MockTasksApi();
    mockTasklists = MockTasklistsResource();
    mockTasks = MockTasksResource();
    when(mockApi.tasklists).thenReturn(mockTasklists);
    when(mockApi.tasks).thenReturn(mockTasks);
    service = GoogleTasksService.forTesting(mockApi);
  });

  group('GoogleTasksService', () {
    group('getOrCreateTaskList', () {
      test('creates new list when no cache and no existing list', () async {
        // tasklists.list returns empty.
        when(
          mockTasklists.list(),
        ).thenAnswer((_) async => gtasks.TaskLists(items: []));
        // tasklists.insert creates a new list.
        when(mockTasklists.insert(any)).thenAnswer(
          (_) async =>
              gtasks.TaskList(id: 'new-list-id', title: 'Agentic Journal'),
        );

        final result = await service.getOrCreateTaskList();
        expect(result, 'new-list-id');
        verify(mockTasklists.insert(any)).called(1);
      });

      test('finds existing list by name', () async {
        // tasklists.list returns a list with matching name.
        when(mockTasklists.list()).thenAnswer(
          (_) async => gtasks.TaskLists(
            items: [
              gtasks.TaskList(id: 'existing-id', title: 'Agentic Journal'),
            ],
          ),
        );

        final result = await service.getOrCreateTaskList();
        expect(result, 'existing-id');
        verifyNever(mockTasklists.insert(any));
      });

      test('uses cached list ID when valid', () async {
        SharedPreferences.setMockInitialValues({
          'google_tasks_list_id': 'cached-id',
        });

        when(mockTasklists.get('cached-id')).thenAnswer(
          (_) async =>
              gtasks.TaskList(id: 'cached-id', title: 'Agentic Journal'),
        );

        final result = await service.getOrCreateTaskList();
        expect(result, 'cached-id');
        verifyNever(mockTasklists.list());
      });

      test('falls through when cached list returns 404', () async {
        SharedPreferences.setMockInitialValues({
          'google_tasks_list_id': 'deleted-id',
        });

        when(
          mockTasklists.get('deleted-id'),
        ).thenThrow(gtasks.DetailedApiRequestError(404, 'Not Found'));
        when(
          mockTasklists.list(),
        ).thenAnswer((_) async => gtasks.TaskLists(items: []));
        when(mockTasklists.insert(any)).thenAnswer(
          (_) async =>
              gtasks.TaskList(id: 'new-after-404', title: 'Agentic Journal'),
        );

        final result = await service.getOrCreateTaskList();
        expect(result, 'new-after-404');
      });
    });

    group('createTask', () {
      test('inserts task and returns IDs', () async {
        when(
          mockTasks.insert(any, 'list-1'),
        ).thenAnswer((_) async => gtasks.Task(id: 'task-123'));

        final result = await service.createTask(
          title: 'Buy milk',
          taskListId: 'list-1',
        );

        expect(result.googleTaskId, 'task-123');
        expect(result.googleTaskListId, 'list-1');
      });

      test('passes notes and dueDate', () async {
        gtasks.Task? capturedTask;
        when(mockTasks.insert(any, 'list-1')).thenAnswer((inv) async {
          capturedTask = inv.positionalArguments[0] as gtasks.Task;
          return gtasks.Task(id: 'task-456');
        });

        await service.createTask(
          title: 'Call dentist',
          notes: 'Schedule for next week',
          dueDate: DateTime.utc(2026, 3, 10),
          taskListId: 'list-1',
        );

        expect(capturedTask?.title, 'Call dentist');
        expect(capturedTask?.notes, 'Schedule for next week');
        expect(capturedTask?.due, isNotNull);
      });

      test('throws GoogleTasksException on API error', () async {
        when(
          mockTasks.insert(any, 'list-1'),
        ).thenThrow(gtasks.DetailedApiRequestError(403, 'Forbidden'));

        expect(
          () => service.createTask(title: 'Test', taskListId: 'list-1'),
          throwsA(isA<GoogleTasksException>()),
        );
      });

      test('throws GoogleTasksException when task has no ID', () async {
        when(
          mockTasks.insert(any, 'list-1'),
        ).thenAnswer((_) async => gtasks.Task(id: null));

        expect(
          () => service.createTask(title: 'Test', taskListId: 'list-1'),
          throwsA(isA<GoogleTasksException>()),
        );
      });
    });

    group('completeTask', () {
      test('patches task with completed status', () async {
        when(mockTasks.patch(any, 'list-1', 'task-1')).thenAnswer(
          (_) async => gtasks.Task(id: 'task-1', status: 'completed'),
        );

        await service.completeTask(
          googleTaskId: 'task-1',
          taskListId: 'list-1',
        );

        final captured =
            verify(
                  mockTasks.patch(captureAny, 'list-1', 'task-1'),
                ).captured.single
                as gtasks.Task;
        expect(captured.status, 'completed');
      });

      test('throws GoogleTasksException on API error', () async {
        when(
          mockTasks.patch(any, 'list-1', 'task-1'),
        ).thenThrow(gtasks.DetailedApiRequestError(500, 'Server Error'));

        expect(
          () => service.completeTask(
            googleTaskId: 'task-1',
            taskListId: 'list-1',
          ),
          throwsA(isA<GoogleTasksException>()),
        );
      });
    });

    group('updateTask', () {
      test('patches task with provided fields', () async {
        when(
          mockTasks.patch(any, 'list-1', 'task-1'),
        ).thenAnswer((_) async => gtasks.Task(id: 'task-1'));

        await service.updateTask(
          googleTaskId: 'task-1',
          taskListId: 'list-1',
          title: 'Updated title',
          notes: 'Updated notes',
        );

        final captured =
            verify(
                  mockTasks.patch(captureAny, 'list-1', 'task-1'),
                ).captured.single
                as gtasks.Task;
        expect(captured.title, 'Updated title');
        expect(captured.notes, 'Updated notes');
      });

      test('throws GoogleTasksException on API error', () async {
        when(
          mockTasks.patch(any, 'list-1', 'task-1'),
        ).thenThrow(gtasks.DetailedApiRequestError(404, 'Not Found'));

        expect(
          () =>
              service.updateTask(googleTaskId: 'task-1', taskListId: 'list-1'),
          throwsA(isA<GoogleTasksException>()),
        );
      });
    });

    group('deleteTask', () {
      test('calls delete on API', () async {
        when(mockTasks.delete('list-1', 'task-1')).thenAnswer((_) async {});

        await service.deleteTask(googleTaskId: 'task-1', taskListId: 'list-1');

        verify(mockTasks.delete('list-1', 'task-1')).called(1);
      });

      test('throws GoogleTasksException on API error', () async {
        when(
          mockTasks.delete('list-1', 'task-1'),
        ).thenThrow(gtasks.DetailedApiRequestError(404, 'Not Found'));

        expect(
          () =>
              service.deleteTask(googleTaskId: 'task-1', taskListId: 'list-1'),
          throwsA(isA<GoogleTasksException>()),
        );
      });
    });
  });

  group('TaskCreateResult', () {
    test('stores task and list IDs', () {
      const result = TaskCreateResult(
        googleTaskId: 'task-abc',
        googleTaskListId: 'list-xyz',
      );
      expect(result.googleTaskId, 'task-abc');
      expect(result.googleTaskListId, 'list-xyz');
    });
  });

  group('GoogleTasksException', () {
    test('toString includes message', () {
      const e = GoogleTasksException('test error');
      expect(e.toString(), contains('test error'));
    });
  });
}
