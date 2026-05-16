import 'dart:math';

import 'track.dart';

class BaseParams {
  final int hrBase;
  final int cadenceBase;

  const BaseParams({required this.hrBase, required this.cadenceBase});
}

class GenerationParams {
  final double distMin;
  final double distMax;
  final double durMin;
  final double durMax;
  final DateTime dateStart;
  final DateTime dateEnd;
  final int timeStartMinMinutes;
  final int timeStartMaxMinutes;
  final Track track;
  final String outputDir;

  const GenerationParams({
    required this.distMin,
    required this.distMax,
    required this.durMin,
    required this.durMax,
    required this.dateStart,
    required this.dateEnd,
    required this.timeStartMinMinutes,
    required this.timeStartMaxMinutes,
    required this.track,
    required this.outputDir,
  });

  int get totalDays => dateEnd.difference(dateStart).inDays + 1;

  double get centerLat => track.latitude;
  double get centerLon => track.longitude;
  double get trackAngle => track.angle;

  BaseParams calculateBaseParams(double distKm, double durMin) {
    final paceSec = (durMin * 60) / max(distKm, 0.001);
    final rng = Random();
    int hr, cad;
    if (paceSec < 300) {
      hr = 160 + rng.nextInt(16);
      cad = 180 + rng.nextInt(11);
    } else if (paceSec < 360) {
      hr = 145 + rng.nextInt(11);
      cad = 170 + rng.nextInt(11);
    } else {
      hr = 125 + rng.nextInt(16);
      cad = 155 + rng.nextInt(11);
    }
    return BaseParams(hrBase: hr, cadenceBase: cad);
  }

  double randomDistance() {
    final rng = Random();
    return distMin + rng.nextDouble() * (distMax - distMin);
  }

  double randomDuration() {
    final rng = Random();
    return durMin + rng.nextDouble() * (durMax - durMin);
  }

  DateTime randomStartTime(DateTime day) {
    final rng = Random();
    final maxOffsetMinutes = timeStartMaxMinutes - timeStartMinMinutes;
    final randMinutes = rng.nextInt(maxOffsetMinutes + 1);
    return DateTime(
      day.year,
      day.month,
      day.day,
      timeStartMinMinutes ~/ 60,
      timeStartMinMinutes % 60,
    ).add(Duration(minutes: randMinutes));
  }
}
