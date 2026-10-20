/// Roadmap-only interface sketch. This package is not shipped or supported in v1.
library ucve_voice_client;

class UCVEVoiceClientStub {
  final String token;
  final String wsUrl;

  UCVEVoiceClientStub({
    required this.token,
    this.wsUrl = 'ws://localhost:8081/ws/audio',
  }) {
    if (token.isEmpty) {
      throw ArgumentError('Token must not be empty.');
    }
  }

  Future<void> connect() async {
    throw UnsupportedError('Flutter SDK is not available in Wavia v1.');
  }

  Future<void> disconnect() async {
    throw UnsupportedError('Flutter SDK is not available in Wavia v1.');
  }
}
