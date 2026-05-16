import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

import '../models/track.dart';

class TrackRepository {
  static TrackRepository? _instance;
  List<Track> _tracks = [];
  bool _loaded = false;

  TrackRepository._();

  factory TrackRepository() {
    _instance ??= TrackRepository._();
    return _instance!;
  }

  List<Track> get tracks => List.unmodifiable(_tracks);

  Future<void> _ensureLoaded() async {
    if (_loaded) return;
    await load();
  }

  Future<String> get _filePath async {
    final dir = await getApplicationDocumentsDirectory();
    return '${dir.path}/keeptrack_tracks.json';
  }

  Future<void> load() async {
    try {
      final file = File(await _filePath);
      if (await file.exists()) {
        final content = await file.readAsString();
        final list = jsonDecode(content) as List<dynamic>;
        _tracks = list
            .map((e) => Track.fromJson(e as Map<String, dynamic>))
            .toList();
      } else {
        _tracks = List.from(defaultTracks);
        await save();
      }
    } catch (_) {
      _tracks = List.from(defaultTracks);
    }
    _loaded = true;
  }

  Future<void> save() async {
    final file = File(await _filePath);
    final dir = file.parent;
    if (!await dir.exists()) await dir.create(recursive: true);
    final json = jsonEncode(_tracks.map((t) => t.toJson()).toList());
    await file.writeAsString(json);
  }

  Future<void> add(Track track) async {
    await _ensureLoaded();
    _tracks.add(track);
    await save();
  }

  Future<void> update(Track track) async {
    await _ensureLoaded();
    final idx = _tracks.indexWhere((t) => t.id == track.id);
    if (idx != -1) {
      _tracks[idx] = track;
      await save();
    }
  }

  Future<void> delete(String id) async {
    await _ensureLoaded();
    _tracks.removeWhere((t) => t.id == id);
    await save();
  }

  Future<Track?> get(String id) async {
    await _ensureLoaded();
    try {
      return _tracks.firstWhere((t) => t.id == id);
    } catch (_) {
      return null;
    }
  }

  Future<void> ensureDefaults() async {
    await _ensureLoaded();
  }
}
