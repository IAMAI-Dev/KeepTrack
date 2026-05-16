class Track {
  final String id;
  final String name;
  final double latitude;
  final double longitude;
  final double angle;

  const Track({
    required this.id,
    required this.name,
    required this.latitude,
    required this.longitude,
    required this.angle,
  });

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'latitude': latitude,
    'longitude': longitude,
    'angle': angle,
  };

  factory Track.fromJson(Map<String, dynamic> json) => Track(
    id: json['id'] as String,
    name: json['name'] as String,
    latitude: (json['latitude'] as num).toDouble(),
    longitude: (json['longitude'] as num).toDouble(),
    angle: (json['angle'] as num).toDouble(),
  );

  Track copyWith({
    String? id,
    String? name,
    double? latitude,
    double? longitude,
    double? angle,
  }) => Track(
    id: id ?? this.id,
    name: name ?? this.name,
    latitude: latitude ?? this.latitude,
    longitude: longitude ?? this.longitude,
    angle: angle ?? this.angle,
  );
}

const defaultTracks = [
  Track(
    id: 'default_1',
    name: '天津大学(北洋园校区)',
    latitude: 39.001439,
    longitude: 117.314831,
    angle: 0,
  ),

  Track(
    id: 'default_2',
    name: '湖北大学(武昌校区)',
    latitude: 30.5800521,
    longitude: 114.3307788,
    angle: 62.5,
  ),

  Track(
    id: 'default_3',
    name: '湖北大学(阳逻校区)',
    latitude: 30.6464622,
    longitude: 114.5764778,
    angle: -30,
  ),

  Track(
    id: 'default_4',
    name: '广东药科大学(大学城校区)',
    latitude: 23.0580840,
    longitude: 113.4028471,
    angle: 0,
  ),

  Track(
    id: 'default_5',
    name: '山东大学(兴隆山校区)',
    latitude: 36.59728,
    longitude: 117.04467,
    angle: 0,
  ),
];
