import 'dart:math';

class TrackGenerator {
  /// Generates a single track point on a simulated 400m running track.
  ///
  /// [progress] is 0.0 to 1.0 (position within the run).
  /// [totalLaps] is the total number of laps.
  /// [centerLat]/[centerLon] define the center of the track.
  /// [seed] provides deterministic randomness.
  /// [angle] is the track bearing in degrees.
  static (double lat, double lon) trackPoint(
    double progress,
    double totalLaps,
    double centerLat,
    double centerLon,
    int seed,
    double angle,
  ) {
    final rng = Random(seed + (progress * 1000000).toInt());
    final theta = -angle * pi / 180.0;

    const L = 85.0; // straight section length
    const R = 36.5; // curve radius

    final currentLap = progress * totalLaps;
    final lapP = currentLap % 1.0;
    final seg = (lapP * 4).toInt();
    final segP = (lapP * 4) - seg;

    double bx, by;

    switch (seg) {
      case 0: // bottom straight, left to right
        bx = -R;
        by = -L / 2 + L * segP;
      case 1: // right curve, bottom to top
        final ang = pi * (1 - segP);
        bx = R * cos(ang);
        by = L / 2 + R * sin(ang);
      case 2: // top straight, right to left
        bx = R;
        by = L / 2 - L * segP;
      default: // left curve, top to bottom
        final ang = pi * segP;
        bx = R * cos(ang);
        by = -L / 2 - R * sin(ang);
    }

    // Add slight offset to simulate real running
    final off = 1.2 + sin(currentLap) * 0.5;
    final x = bx + off + rng.nextDouble() * 1.0 - 0.5;
    final y = by + rng.nextDouble() * 1.0 - 0.5;

    // Rotate by track angle
    final xr = x * cos(theta) - y * sin(theta);
    final yr = x * sin(theta) + y * cos(theta);

    final lat = centerLat + (yr / 111000.0);
    final lon = centerLon + (xr / (111000.0 * cos(centerLat * pi / 180.0)));

    return (lat, lon);
  }
}
