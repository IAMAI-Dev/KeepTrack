import 'package:flutter_test/flutter_test.dart';

import 'package:keeptrack/main.dart';

void main() {
  testWidgets('App renders correctly', (WidgetTester tester) async {
    await tester.pumpWidget(const KeepTrackApp());
    expect(find.text('KeepTrack'), findsOneWidget);
  });
}
