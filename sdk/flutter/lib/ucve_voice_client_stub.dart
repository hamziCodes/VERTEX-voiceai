/// UCVE Flutter SDK Interface Stub (Roadmap item for Post-v1).
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
    // Planned native channel bridge implementation
  }

  Future<void> disconnect() async {
    // Disconnect transport
  }
}
