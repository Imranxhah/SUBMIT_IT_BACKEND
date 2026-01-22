# Flutter Integration Guide: Home Screen with Swipe-to-Refresh

## 1. Dependencies
Ensure you have `http` and `intl` in your `pubspec.yaml`:
```yaml
dependencies:
  http: ^1.0.0
  intl: ^0.19.0
```

## 2. Data Model
```dart
class SubmissionStatus {
  final int limit;
  final int used;
  final int remaining;
  final DateTime? nextResetTime;

  SubmissionStatus({
    required this.limit,
    required this.used,
    required this.remaining,
    this.nextResetTime,
  });

  factory SubmissionStatus.fromJson(Map<String, dynamic> json) {
    return SubmissionStatus(
      limit: json['limit'],
      used: json['used'],
      remaining: json['remaining'],
      nextResetTime: json['next_reset_time'] != null
          ? DateTime.parse(json['next_reset_time'])
          : null,
    );
  }
}
```

## 3. Home Screen Implementation
This screen handles the **Swipe-to-Refresh** logic and displays the status card.

```dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';

class HomeScreen extends StatefulWidget {
  final String accessToken; // Pass your JWT here

  const HomeScreen({Key? key, required this.accessToken}) : super(key: key);

  @override
  _HomeScreenState createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  SubmissionStatus? _status;
  bool _isLoading = true;
  Timer? _timer;
  Duration _timeUntilReset = Duration.zero;

  @override
  void initState() {
    super.initState();
    _fetchStatus();
    
    // Timer to update the countdown every second without re-fetching
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      if (_status?.nextResetTime != null) {
        _updateTimeRemaining();
      }
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  /// Calculates remaining time for the UI countdown
  void _updateTimeRemaining() {
    if (_status?.nextResetTime == null) return;
    
    final now = DateTime.now().toUtc();
    final remaining = _status!.nextResetTime!.difference(now);

    if (remaining.isNegative) {
      // Timer finished, auto-refresh to update slots
      _fetchStatus();
    } else {
      if (mounted) {
        setState(() {
          _timeUntilReset = remaining;
        });
      }
    }
  }

  /// API Call: Get Status
  Future<void> _fetchStatus() async {
    // If not triggered by RefreshIndicator, show loading (optional)
    // setState(() => _isLoading = true); 
    
    try {
      final response = await http.get(
        Uri.parse('http://YOUR_IP:8000/api/assignments/status/'),
        headers: {'Authorization': 'Bearer ${widget.accessToken}'},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (mounted) {
          setState(() {
            _status = SubmissionStatus.fromJson(data);
            _isLoading = false;
          });
          _updateTimeRemaining();
        }
      }
    } catch (e) {
      print("Error: $e");
      if (mounted) setState(() => _isLoading = false);
    }
  }

  /// API Call: Claim Reward
  Future<void> _watchAdAndClaimReward() async {
    // 1. Trigger your Ad SDK here
    bool adWatched = true; // Simulated

    if (adWatched) {
      try {
        final response = await http.post(
          Uri.parse('http://YOUR_IP:8000/api/assignments/reward/'),
          headers: {'Authorization': 'Bearer ${widget.accessToken}'},
        );

        if (response.statusCode == 200) {
          final data = json.decode(response.body);
          if (mounted) {
            setState(() {
              _status = SubmissionStatus.fromJson(data['status']);
            });
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text("Reward Claimed! +1 Limit Added")),
            );
          }
        }
      } catch (e) {
        print("Error claiming reward: $e");
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Submit It"),
        // No refresh action here, handled by RefreshIndicator
      ),
      body: RefreshIndicator(
        onRefresh: _fetchStatus, // Swipe down triggers this
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // --- Daily Limit Card (Only on Home Screen) ---
            if (_status != null)
              _buildStatusCard()
            else if (_isLoading)
              const Center(child: CircularProgressIndicator())
            else
              const Center(child: Text("Failed to load status. Swipe to retry.")),
            
            const SizedBox(height: 20),
            
            // --- Other Home Screen Content ---
            ListTile(
              leading: const Icon(Icons.note_add),
              title: const Text("Generate New Assignment"),
              subtitle: const Text("Create a new PDF submission"),
              onTap: () {
                 // Navigate to Generate Page (WITHOUT the status card)
                 // Navigator.push(...);
              },
            ),
             ListTile(
              leading: const Icon(Icons.history),
              title: const Text("History"),
              subtitle: const Text("View past submissions"),
              onTap: () {},
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusCard() {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            const Text(
              "Daily Submissions",
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStatItem("Used", "${_status!.used}", Colors.black),
                _buildStatItem("Remaining", "${_status!.remaining}", Colors.green),
                _buildStatItem("Limit", "${_status!.limit}", Colors.black),
              ],
            ),
            
            // Show countdown if limit reached or slot pending
            if (_status!.nextResetTime != null) ...[
              const SizedBox(height: 16),
              const Divider(),
              const SizedBox(height: 8),
              const Text("Next slot available in:", style: TextStyle(color: Colors.grey)),
              Text(
                _formatDuration(_timeUntilReset),
                style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.blue),
              ),
            ],

            // Show Ad Button if limit reached (or always, depending on your logic)
            if (_status!.remaining == 0) ...[
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: _watchAdAndClaimReward,
                  icon: const Icon(Icons.play_circle_fill),
                  label: const Text("Watch Ad (+1 Limit)"),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.purple,
                    foregroundColor: Colors.white,
                  ),
                ),
              ),
            ]
          ],
        ),
      ),
    );
  }

  Widget _buildStatItem(String label, String value, Color color) {
    return Column(
      children: [
        Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
        Text(label, style: const TextStyle(color: Colors.grey)),
      ],
    );
  }

  String _formatDuration(Duration d) {
    String twoDigits(int n) => n.toString().padLeft(2, "0");
    String hours = twoDigits(d.inHours);
    String minutes = twoDigits(d.inMinutes.remainder(60));
    String seconds = twoDigits(d.inSeconds.remainder(60));
    return "$hours:$minutes:$seconds";
  }
}
```