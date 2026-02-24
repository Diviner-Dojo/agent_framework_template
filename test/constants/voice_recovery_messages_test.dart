import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/constants/voice_recovery_messages.dart';

void main() {
  group('VoiceRecoveryMessages', () {
    test('all messages are non-empty strings', () {
      final messages = [
        VoiceRecoveryMessages.greeting,
        VoiceRecoveryMessages.welcomeBack,
        VoiceRecoveryMessages.sessionEndConfirm,
        VoiceRecoveryMessages.sessionEndComplete,
        VoiceRecoveryMessages.endSessionConfirmPrompt,
        VoiceRecoveryMessages.verbalDiscardConfirm,
        VoiceRecoveryMessages.discardComplete,
        VoiceRecoveryMessages.confirmationCancelled,
        VoiceRecoveryMessages.undoAvailable,
        VoiceRecoveryMessages.undoExpired,
        VoiceRecoveryMessages.undoSuccess,
        VoiceRecoveryMessages.sttFailure,
        VoiceRecoveryMessages.sttEmpty,
        VoiceRecoveryMessages.llmThinking,
        VoiceRecoveryMessages.processingError,
        VoiceRecoveryMessages.paused,
        VoiceRecoveryMessages.interrupted,
      ];

      for (final msg in messages) {
        expect(msg, isNotEmpty);
      }
    });
  });
}
