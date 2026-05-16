import 'package:flutter/material.dart';

import '../models/track.dart';
import '../services/track_repository.dart';

class TrackManageScreen extends StatefulWidget {
  const TrackManageScreen({super.key});

  @override
  State<TrackManageScreen> createState() => _TrackManageScreenState();
}

class _TrackManageScreenState extends State<TrackManageScreen> {
  final _repo = TrackRepository();
  List<Track> _tracks = [];
  bool _loading = true;

  // Form state
  final _nameCtrl = TextEditingController();
  final _latCtrl = TextEditingController();
  final _lonCtrl = TextEditingController();
  final _angleCtrl = TextEditingController();
  final _formKey = GlobalKey<FormState>();
  String? _editingId;

  bool get _isEditing => _editingId != null;

  @override
  void initState() {
    super.initState();
    _loadTracks();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _latCtrl.dispose();
    _lonCtrl.dispose();
    _angleCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadTracks() async {
    await _repo.load();
    setState(() {
      _tracks = _repo.tracks;
      _loading = false;
    });
  }

  void _startEdit(Track track) {
    _nameCtrl.text = track.name;
    _latCtrl.text = track.latitude.toString();
    _lonCtrl.text = track.longitude.toString();
    _angleCtrl.text = track.angle.toString();
    setState(() => _editingId = track.id);
  }

  void _clearForm() {
    _nameCtrl.clear();
    _latCtrl.clear();
    _lonCtrl.clear();
    _angleCtrl.clear();
    setState(() => _editingId = null);
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;

    final track = Track(
      id: _editingId ?? DateTime.now().millisecondsSinceEpoch.toString(),
      name: _nameCtrl.text.trim(),
      latitude: double.parse(_latCtrl.text.trim()),
      longitude: double.parse(_lonCtrl.text.trim()),
      angle: double.parse(_angleCtrl.text.trim()),
    );

    if (_isEditing) {
      await _repo.update(track);
    } else {
      await _repo.add(track);
    }
    _clearForm();
    _loadTracks();
  }

  Future<void> _delete(Track track) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除操场'),
        content: Text('确定要删除「${track.name}」吗？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
    if (confirmed == true) {
      await _repo.delete(track.id);
      if (_editingId == track.id) _clearForm();
      _loadTracks();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('管理操场'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                // Add/Edit form
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Row(
                          children: [
                            Icon(
                              _isEditing ? Icons.edit_location_alt : Icons.add_location_alt,
                              color: Theme.of(context).colorScheme.primary,
                            ),
                            const SizedBox(width: 8),
                            Text(
                              _isEditing ? '编辑操场' : '添加新操场',
                              style: Theme.of(context).textTheme.titleSmall,
                            ),
                            const Spacer(),
                            if (_isEditing)
                              TextButton.icon(
                                onPressed: _clearForm,
                                icon: const Icon(Icons.close, size: 16),
                                label: const Text('取消编辑'),
                              ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _nameCtrl,
                          decoration: const InputDecoration(
                            labelText: '操场名称',
                            hintText: '例如: 武汉理工大学操场',
                            border: OutlineInputBorder(),
                            isDense: true,
                          ),
                          validator: (v) => (v == null || v.trim().isEmpty) ? '请输入名称' : null,
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: TextFormField(
                                controller: _latCtrl,
                                decoration: const InputDecoration(
                                  labelText: '中心纬度',
                                  hintText: '30.5800521',
                                  border: OutlineInputBorder(),
                                  isDense: true,
                                ),
                                keyboardType: TextInputType.number,
                                validator: (v) {
                                  final n = double.tryParse(v ?? '');
                                  if (n == null || n < -90 || n > 90) return '无效纬度';
                                  return null;
                                },
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: TextFormField(
                                controller: _lonCtrl,
                                decoration: const InputDecoration(
                                  labelText: '中心经度',
                                  hintText: '114.3307788',
                                  border: OutlineInputBorder(),
                                  isDense: true,
                                ),
                                keyboardType: TextInputType.number,
                                validator: (v) {
                                  final n = double.tryParse(v ?? '');
                                  if (n == null || n < -180 || n > 180) return '无效经度';
                                  return null;
                                },
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        TextFormField(
                          controller: _angleCtrl,
                          decoration: const InputDecoration(
                            labelText: '跑道方位角 (度)',
                            hintText: '62.5',
                            border: OutlineInputBorder(),
                            isDense: true,
                          ),
                          keyboardType: TextInputType.number,
                          validator: (v) {
                            final n = double.tryParse(v ?? '');
                            if (n == null || n < 0 || n > 360) return '角度需在0-360之间';
                            return null;
                          },
                        ),
                        const SizedBox(height: 12),
                        FilledButton.icon(
                          onPressed: _save,
                          icon: Icon(_isEditing ? Icons.save : Icons.add),
                          label: Text(_isEditing ? '保存修改' : '添加操场'),
                        ),
                      ],
                    ),
                  ),
                ),
                // Divider
                const Divider(height: 1),
                // Track list
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      Text('已保存的操场 (${_tracks.length})',
                          style: Theme.of(context).textTheme.labelLarge),
                    ],
                  ),
                ),
                Expanded(
                  child: _tracks.isEmpty
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(32),
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.stadium, size: 48, color: Colors.grey[400]),
                                const SizedBox(height: 8),
                                const Text('还没有操场', style: TextStyle(color: Colors.grey)),
                                const Text('使用上方表单添加', style: TextStyle(color: Colors.grey, fontSize: 12)),
                              ],
                            ),
                          ),
                        )
                      : ListView.builder(
                          itemCount: _tracks.length,
                          padding: const EdgeInsets.only(bottom: 80),
                          itemBuilder: (_, i) {
                            final track = _tracks[i];
                            final isSelected = _editingId == track.id;
                            return Card(
                              color: isSelected ? Theme.of(context).colorScheme.primaryContainer : null,
                              child: ListTile(
                                leading: Icon(
                                  Icons.stadium,
                                  color: isSelected
                                      ? Theme.of(context).colorScheme.primary
                                      : null,
                                ),
                                title: Text(track.name),
                                subtitle: Text(
                                  '${track.latitude}, ${track.longitude}  |  方位角 ${track.angle}°',
                                  style: const TextStyle(fontSize: 12),
                                ),
                                trailing: Row(
                                  mainAxisSize: MainAxisSize.min,
                                  children: [
                                    IconButton(
                                      icon: const Icon(Icons.edit, size: 20),
                                      onPressed: () => _startEdit(track),
                                    ),
                                    IconButton(
                                      icon: const Icon(Icons.delete_outline, size: 20),
                                      onPressed: () => _delete(track),
                                    ),
                                  ],
                                ),
                              ),
                            );
                          },
                        ),
                ),
              ],
            ),
    );
  }
}
