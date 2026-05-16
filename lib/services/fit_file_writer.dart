import 'dart:io';
import 'dart:math';

import 'package:fit_tool/fit_tool.dart';

import '../models/generation_params.dart';
import 'track_generator.dart';

class FitFileWriter {
  /// Generate a single FIT file and return the file path.
  static Future<String> generateFitFile({
    required GenerationParams params,
    required int index,
    required double distKm,
    required double durMin,
    required DateTime startTime,
  }) async {
    final builder = FitFileBuilder(autoDefine: true);

    final startTs = startTime.millisecondsSinceEpoch;
    final durSec = durMin * 60;
    final distM = distKm * 1000;

    // File ID
    final fileId = FileIdMessage()
      ..type = FileType.activity
      ..manufacturer = Manufacturer.garmin.value
      ..timeCreated = startTs;
    builder.add(fileId);

    // Calculate base params
    final baseParams = params.calculateBaseParams(distKm, durMin);

    // Records (one every ~2 seconds)
    final numPts = max(20, durSec ~/ 2);
    final laps = distM / 400.0;
    final seed = Random().nextInt(99999);

    for (var i = 0; i < numPts; i++) {
      final p = i / (numPts - 1);
      final (currLat, currLon) = TrackGenerator.trackPoint(
        p,
        laps,
        params.centerLat,
        params.centerLon,
        seed,
        params.trackAngle,
      );

      final record = RecordMessage()
        ..timestamp = startTs + (p * durSec * 1000).toInt()
        ..positionLat = currLat
        ..positionLong = currLon
        ..distance = distM * p
        ..speed = (distM / durSec) + Random().nextDouble() * 0.2 - 0.1
        ..heartRate = baseParams.hrBase + Random().nextInt(5) - 2
        ..cadence = baseParams.cadenceBase + Random().nextInt(3) - 1;

      builder.add(record);
    }

    // Session
    final session = SessionMessage()
      ..timestamp = startTs + (durSec * 1000).toInt()
      ..startTime = startTs
      ..totalElapsedTime = durSec
      ..totalDistance = distM
      ..sport = Sport.running
      ..avgHeartRate = baseParams.hrBase
      ..totalCalories = (distKm * 65).toInt();
    builder.add(session);

    final fitFile = builder.build();
    final bytes = fitFile.toBytes();

    final fileName = 'run_${_formatTimestamp(startTime)}.fit';
    final filePath = '${params.outputDir}/$fileName';
    final file = File(filePath);
    await file.writeAsBytes(bytes);

    return filePath;
  }

  static String _formatTimestamp(DateTime dt) {
    final y = dt.year.toString();
    final m = dt.month.toString().padLeft(2, '0');
    final d = dt.day.toString().padLeft(2, '0');
    final h = dt.hour.toString().padLeft(2, '0');
    final min = dt.minute.toString().padLeft(2, '0');
    return '$y$m${d}_$h$min';
  }
}
