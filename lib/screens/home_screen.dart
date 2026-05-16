import 'dart:io';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../models/generation_params.dart';
import '../models/track.dart';
import '../services/fit_file_writer.dart';
import '../services/track_repository.dart';

import 'track_manage_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _repo = TrackRepository();

  // Distance
  final _distMinCtrl = TextEditingController(text: '5.00');
  final _distMaxCtrl = TextEditingController(text: '5.00');
  // Duration
  final _durMinCtrl = TextEditingController(text: '30');
  final _durMaxCtrl = TextEditingController(text: '30');
  // Date range
  late DateTime _dateStart;
  late DateTime _dateEnd;
  // Time range
  final _timeStartMinCtrl = TextEditingController(text: '07:00');
  final _timeStartMaxCtrl = TextEditingController(text: '09:00');
  // Track
  List<Track> _tracks = [];
  Track? _selectedTrack;
  // Output
  String _outputDir = '';

  bool _generating = false;
  double _progress = 0.0;
  final List<String> _logs = [];

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _dateStart = now;
    _dateEnd = now.add(const Duration(days: 7));
    _initData();
  }

  Future<void> _initData() async {
    await _repo.ensureDefaults();
    final tracks = _repo.tracks;
    final dir = await getApplicationDocumentsDirectory();
    setState(() {
      _tracks = tracks;
      if (tracks.isNotEmpty) _selectedTrack = tracks.first;
      _outputDir = '${dir.path}/Keep运动数据';
    });
  }

  Future<void> _refreshTracks() async {
    await _repo.load();
    setState(() {
      _tracks = _repo.tracks;
      if (_selectedTrack != null) {
        final stillExists = _tracks.any((t) => t.id == _selectedTrack!.id);
        if (!stillExists) {
          _selectedTrack = _tracks.isNotEmpty ? _tracks.first : null;
        }
      } else if (_tracks.isNotEmpty) {
        _selectedTrack = _tracks.first;
      }
    });
  }

  @override
  void dispose() {
    _distMinCtrl.dispose();
    _distMaxCtrl.dispose();
    _durMinCtrl.dispose();
    _durMaxCtrl.dispose();
    _timeStartMinCtrl.dispose();
    _timeStartMaxCtrl.dispose();
    super.dispose();
  }

  void _log(String msg) {
    setState(() {
      final ts = DateFormat('HH:mm:ss').format(DateTime.now());
      _logs.add('[$ts] $msg');
    });
  }

  // ─── Log bottom sheet ──────────────────────────────────────

  void _showLogSheet() {
    if (_logs.isEmpty) return;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (_) {
        return DraggableScrollableSheet(
          initialChildSize: 0.6,
          minChildSize: 0.3,
          maxChildSize: 0.9,
          expand: false,
          builder: (ctx, scrollController) {
            return Column(
              children: [
                // Handle bar
                Padding(
                  padding: const EdgeInsets.only(top: 8, bottom: 4),
                  child: Container(
                    width: 32,
                    height: 4,
                    decoration: BoxDecoration(
                      color: Colors.grey[300],
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                ),
                // Header
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      const Icon(Icons.terminal, size: 18),
                      const SizedBox(width: 8),
                      Text('运行日志 (${_logs.length})',
                          style: Theme.of(context).textTheme.titleSmall),
                      const Spacer(),
                      GestureDetector(
                        onTap: () {
                          setState(() => _logs.clear());
                          Navigator.pop(ctx);
                        },
                        child: const Icon(Icons.clear_all, size: 20),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1),
                // Log content
                Expanded(
                  child: ListView.builder(
                    controller: scrollController,
                    padding: const EdgeInsets.all(12),
                    itemCount: _logs.length,
                    itemBuilder: (_, i) => SelectableText(
                      _logs[i],
                      style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                    ),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  // ─── Date picker ───────────────────────────────────────────

  Future<void> _pickDate(bool isStart) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: isStart ? _dateStart : _dateEnd,
      firstDate: DateTime(2020),
      lastDate: now.add(const Duration(days: 365)),
      helpText: isStart ? '选择开始日期' : '选择结束日期',
      cancelText: '取消',
      confirmText: '确认',
    );
    if (picked != null) {
      setState(() {
        if (isStart) {
          _dateStart = picked;
          if (_dateEnd.isBefore(_dateStart)) _dateEnd = _dateStart;
        } else {
          _dateEnd = picked;
          if (_dateEnd.isBefore(_dateStart)) _dateStart = _dateEnd;
        }
      });
    }
  }

  // ─── Build params & validate ───────────────────────────────

  GenerationParams? _buildParams() {
    try {
      final timeStartParts = _timeStartMinCtrl.text.trim().split(':');
      final timeEndParts = _timeStartMaxCtrl.text.trim().split(':');
      final timeStartMin = int.parse(timeStartParts[0]) * 60 + int.parse(timeStartParts[1]);
      final timeEndMin = int.parse(timeEndParts[0]) * 60 + int.parse(timeEndParts[1]);

      if (_selectedTrack == null) return null;

      return GenerationParams(
        distMin: double.parse(_distMinCtrl.text.trim()),
        distMax: double.parse(_distMaxCtrl.text.trim()),
        durMin: double.parse(_durMinCtrl.text.trim()),
        durMax: double.parse(_durMaxCtrl.text.trim()),
        dateStart: _dateStart,
        dateEnd: _dateEnd,
        timeStartMinMinutes: timeStartMin,
        timeStartMaxMinutes: timeEndMin,
        track: _selectedTrack!,
        outputDir: _outputDir,
      );
    } catch (_) {
      return null;
    }
  }

  // ─── Generation ────────────────────────────────────────────

  Future<void> _startGeneration() async {
    final params = _buildParams();
    if (params == null) {
      _showError('请检查所有输入参数是否正确填写');
      return;
    }
    if (_selectedTrack == null) {
      _showError('请先选择一个操场');
      return;
    }
    if (_outputDir.isEmpty) {
      _showError('输出目录未设置');
      return;
    }

    setState(() {
      _generating = true;
      _progress = 0.0;
      _logs.clear();
    });

    try {
      final dir = Directory(params.outputDir);
      if (!await dir.exists()) await dir.create(recursive: true);

      final totalDays = params.totalDays;
      for (var i = 0; i < totalDays; i++) {
        final currentDay = DateTime(
          params.dateStart.year,
          params.dateStart.month,
          params.dateStart.day + i,
        );

        final dist = params.randomDistance();
        final dur = params.randomDuration();
        final startTime = params.randomStartTime(currentDay);

        _log('Day ${i + 1}/$totalDays: ${DateFormat('yyyy-MM-dd').format(currentDay)} | '
            '距离: ${dist.toStringAsFixed(2)}km | 开始: ${DateFormat('HH:mm').format(startTime)}');

        await FitFileWriter.generateFitFile(
          params: params,
          index: i,
          distKm: dist,
          durMin: dur,
          startTime: startTime,
        );

        setState(() => _progress = (i + 1) / totalDays);
        await Future.delayed(Duration.zero);
      }

      _log('全部完成! 生成了 $totalDays 天的运动数据');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('成功生成 $totalDays 天的数据!'),
            action: SnackBarAction(label: '分享', onPressed: _shareFiles),
          ),
        );
      }
    } catch (e) {
      _log('错误: $e');
      _showError('生成失败: $e');
    } finally {
      setState(() {
        _generating = false;
        _progress = 0.0;
      });
    }
  }

  // ─── Share ─────────────────────────────────────────────────

  Future<void> _shareFiles() async {
    try {
      final dir = Directory(_outputDir);
      if (await dir.exists()) {
        final files = await dir.list().where((f) => f.path.endsWith('.fit')).toList();
        if (files.isNotEmpty) {
          final xFiles = files.map((f) => XFile(f.path)).toList();
          await SharePlus.instance.share(ShareParams(files: xFiles));
        }
      }
    } catch (e) {
      _log('分享失败: $e');
    }
  }

  void _showError(String msg) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg), backgroundColor: Colors.red),
      );
    }
  }

  // ─── Navigate to track management ──────────────────────────

  Future<void> _openTrackManager() async {
    await Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const TrackManageScreen()),
    );
    _refreshTracks();
  }

  // ─── Format helpers ────────────────────────────────────────

  String get _dateStartStr => DateFormat('yyyy-MM-dd').format(_dateStart);
  String get _dateEndStr => DateFormat('yyyy-MM-dd').format(_dateEnd);

  // ════════════════════════════════════════════════════════════
  //  BUILD
  // ════════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('KeepTrack'),
        centerTitle: true,
        actions: [
          if (_logs.isNotEmpty)
            _LogBadge(count: _logs.length, onTap: _showLogSheet),
          IconButton(
            icon: const Icon(Icons.info_outline),
            tooltip: '关于',
            onPressed: () => _showAbout(),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 80),
        children: [
          _buildBanner(),
          const SizedBox(height: 16),
          _buildDistanceDurationCard(),
          const SizedBox(height: 12),
          _buildDateTimeCard(),
          const SizedBox(height: 12),
          _buildTrackSelectorCard(),
          const SizedBox(height: 12),
          _buildOutputCard(),
          const SizedBox(height: 20),
          _buildGenerateButton(),
          if (_generating) ...[
            const SizedBox(height: 16),
            _buildProgress(),
          ],
        ],
      ),
      floatingActionButton: _logs.isNotEmpty
          ? FloatingActionButton.small(
              onPressed: _showLogSheet,
              tooltip: '查看日志',
              child: Badge(
                label: Text('${_logs.length}'),
                child: const Icon(Icons.terminal),
              ),
            )
          : null,
    );
  }

  // ─── Banner ────────────────────────────────────────────────

  Widget _buildBanner() {
    final cs = Theme.of(context).colorScheme;
    return Card(
      color: cs.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: Image.asset('assets/icon/logo.png', width: 64, height: 64),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('KeepTrack',
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 2),
                  Text(
                    '模拟跑步数据生成器 · 指定日期范围，每日自动生成随机轨迹',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: cs.onPrimaryContainer.withAlpha(180),
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Distance & Duration ───────────────────────────────────

  Widget _buildDistanceDurationCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.fitness_center, '运动数据随机区间'),
            const SizedBox(height: 12),
            _rangeField('单次距离 (km)', _distMinCtrl, _distMaxCtrl),
            const SizedBox(height: 12),
            _rangeField('单次时长 (min)', _durMinCtrl, _durMaxCtrl),
          ],
        ),
      ),
    );
  }

  // ─── Date & Time ───────────────────────────────────────────

  Widget _buildDateTimeCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.calendar_month, '日期与时间范围'),
            const SizedBox(height: 12),
            Row(
              children: [
                const SizedBox(
                    width: 90,
                    child: Text('日期范围', style: TextStyle(fontSize: 14))),
                Expanded(child: _dateTile(_dateStartStr, () => _pickDate(true))),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 8),
                  child: Text('至', style: TextStyle(color: Colors.grey)),
                ),
                Expanded(child: _dateTile(_dateEndStr, () => _pickDate(false))),
              ],
            ),
            const SizedBox(height: 12),
            _rangeField(
                '每日起始时间', _timeStartMinCtrl, _timeStartMaxCtrl, hint: 'HH:MM'),
          ],
        ),
      ),
    );
  }

  Widget _dateTile(String text, VoidCallback onTap) {
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: _generating ? null : onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(text, style: const TextStyle(fontSize: 14)),
              const Icon(Icons.calendar_today, size: 16, color: Colors.grey),
            ],
          ),
        ),
      ),
    );
  }

  // ─── Track Selector ────────────────────────────────────────

  Widget _buildTrackSelectorCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.stadium, '操场选择'),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    key: ValueKey('track_${_selectedTrack?.id}_${_tracks.length}'),
                    initialValue: _selectedTrack?.id,
                    decoration: const InputDecoration(
                      border: OutlineInputBorder(),
                      contentPadding:
                          EdgeInsets.symmetric(horizontal: 12, vertical: 14),
                      isDense: true,
                    ),
                    hint: const Text('选择操场'),
                    items: _tracks.map((t) {
                      return DropdownMenuItem(
                          value: t.id, child: Text(t.name));
                    }).toList(),
                    onChanged: _generating
                        ? null
                        : (id) {
                            setState(() {
                              _selectedTrack =
                                  _tracks.firstWhere((t) => t.id == id);
                            });
                          },
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _generating ? null : _openTrackManager,
                  icon: const Icon(Icons.add, size: 20),
                  tooltip: '管理操场',
                ),
              ],
            ),
            if (_selectedTrack != null) ...[
              const SizedBox(height: 8),
              Text(
                '${_selectedTrack!.name}  |  '
                '${_selectedTrack!.latitude}, ${_selectedTrack!.longitude}  |  '
                '方位角 ${_selectedTrack!.angle}°',
                style: Theme.of(context)
                    .textTheme
                    .bodySmall
                    ?.copyWith(color: Colors.grey),
              ),
            ],
          ],
        ),
      ),
    );
  }

  // ─── Output Directory ──────────────────────────────────────

  Widget _buildOutputCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionHeader(Icons.folder_outlined, '输出目录'),
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.folder, size: 20, color: Colors.grey[600]),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _outputDir.isEmpty ? '正在设置...' : _outputDir,
                    style: TextStyle(fontSize: 13, color: Colors.grey[700]),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 8),
                TextButton.icon(
                  onPressed: _shareFiles,
                  icon: const Icon(Icons.share, size: 16),
                  label: const Text('分享文件'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  // ─── Generate Button + Progress ────────────────────────────

  Widget _buildGenerateButton() {
    return SizedBox(
      height: 48,
      child: FilledButton.icon(
        onPressed: _generating ? null : _startGeneration,
        icon: _generating
            ? const SizedBox(
                width: 18,
                height: 18,
                child:
                    CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
              )
            : const Icon(Icons.play_arrow),
        label: Text(_generating ? '正在生成...' : '开始按天批量生成'),
      ),
    );
  }

  Widget _buildProgress() {
    return Column(
      children: [
        LinearProgressIndicator(value: _progress),
        const SizedBox(height: 6),
        Text('${(_progress * 100).toStringAsFixed(0)}%',
            style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }

  // ─── Helpers ───────────────────────────────────────────────

  Widget _sectionHeader(IconData icon, String title) {
    return Row(
      children: [
        Icon(icon, size: 20, color: Theme.of(context).colorScheme.primary),
        const SizedBox(width: 8),
        Text(title, style: Theme.of(context).textTheme.titleSmall),
      ],
    );
  }

  Widget _rangeField(String label, TextEditingController minCtrl,
      TextEditingController maxCtrl, {String? hint}) {
    return Row(
      children: [
        SizedBox(
            width: 100, child: Text(label, style: const TextStyle(fontSize: 14))),
        Expanded(
          child: TextField(
            controller: minCtrl,
            decoration: InputDecoration(
              isDense: true,
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
              hintText: hint,
            ),
            keyboardType: TextInputType.number,
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 8),
          child: Text('~', style: TextStyle(color: Colors.grey)),
        ),
        Expanded(
          child: TextField(
            controller: maxCtrl,
            decoration: InputDecoration(
              isDense: true,
              border: const OutlineInputBorder(),
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
              hintText: hint,
            ),
            keyboardType: TextInputType.number,
          ),
        ),
      ],
    );
  }

  void _showAbout() {
    showAboutDialog(
      context: context,
      applicationName: 'KeepTrack',
      applicationVersion: '1.0.0',
      children: [
        const Text('一款模拟跑步轨迹数据生成工具。'
            '可在指定日期范围内，按照用户设定的参数批量生成符合 Garmin 标准的 .fit 文件。'),
      ],
    );
  }
}

/// A compact log badge widget shown in the AppBar.
class _LogBadge extends StatelessWidget {
  final int count;
  final VoidCallback onTap;

  const _LogBadge({required this.count, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Badge(
        label: Text('$count'),
        child: IconButton(
          icon: const Icon(Icons.terminal),
          tooltip: '查看日志',
          onPressed: onTap,
        ),
      ),
    );
  }
}
