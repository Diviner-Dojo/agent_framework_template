import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/models/sync_status.dart';
import 'package:agentic_journal/ui/widgets/sync_status_indicator.dart';

void main() {
  Widget buildTestWidget(SyncStatus status) {
    return MaterialApp(
      home: Scaffold(body: SyncStatusIndicator(status: status)),
    );
  }

  group('SyncStatusIndicator', () {
    testWidgets('shows cloud_done icon for synced status', (tester) async {
      await tester.pumpWidget(buildTestWidget(SyncStatus.synced));

      final icon = tester.widget<Icon>(find.byType(Icon));
      expect(icon.icon, Icons.cloud_done);
      expect(icon.color, Colors.green);
    });

    testWidgets('shows cloud_upload icon for pending status', (tester) async {
      await tester.pumpWidget(buildTestWidget(SyncStatus.pending));

      final icon = tester.widget<Icon>(find.byType(Icon));
      expect(icon.icon, Icons.cloud_upload_outlined);
      expect(icon.color, Colors.grey);
    });

    testWidgets('shows cloud_off icon for failed status', (tester) async {
      await tester.pumpWidget(buildTestWidget(SyncStatus.failed));

      final icon = tester.widget<Icon>(find.byType(Icon));
      expect(icon.icon, Icons.cloud_off);
      expect(icon.color, Colors.red);
    });

    testWidgets('has tooltip with status description', (tester) async {
      await tester.pumpWidget(buildTestWidget(SyncStatus.synced));

      final tooltip = tester.widget<Tooltip>(find.byType(Tooltip));
      expect(tooltip.message, 'Synced');
    });

    testWidgets('pending tooltip says "Pending sync"', (tester) async {
      await tester.pumpWidget(buildTestWidget(SyncStatus.pending));

      final tooltip = tester.widget<Tooltip>(find.byType(Tooltip));
      expect(tooltip.message, 'Pending sync');
    });

    testWidgets('failed tooltip says "Sync failed"', (tester) async {
      await tester.pumpWidget(buildTestWidget(SyncStatus.failed));

      final tooltip = tester.widget<Tooltip>(find.byType(Tooltip));
      expect(tooltip.message, 'Sync failed');
    });

    testWidgets('respects custom size', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: const SyncStatusIndicator(
              status: SyncStatus.synced,
              size: 24,
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byType(Icon));
      expect(icon.size, 24);
    });

    testWidgets('default size is 16', (tester) async {
      await tester.pumpWidget(buildTestWidget(SyncStatus.synced));

      final icon = tester.widget<Icon>(find.byType(Icon));
      expect(icon.size, 16);
    });
  });
}
