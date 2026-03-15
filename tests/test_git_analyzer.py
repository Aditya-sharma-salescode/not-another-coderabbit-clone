"""Tests for git_analyzer — diff parsing and file ordering."""

from reviewer.git_analyzer import (
    ChangedFile,
    extract_commit_log,
    get_diff_text,
    order_files_for_review,
    parse_unified_diff,
    should_skip_file,
)

SAMPLE_DIFF = """\
diff --git a/lib/features/cart/model/cart_item.dart b/lib/features/cart/model/cart_item.dart
index abc1234..def5678 100644
--- a/lib/features/cart/model/cart_item.dart
+++ b/lib/features/cart/model/cart_item.dart
@@ -10,6 +10,8 @@ class CartItem {
   final String name;
   final int quantity;
+  final double price;
+  final String sku;

   CartItem({
     required this.name,
@@ -20,4 +22,6 @@ class CartItem {
   }) : assert(quantity > 0);

+  double get total => price * quantity;
+
   @override
diff --git a/lib/features/cart/services/cart_service.dart b/lib/features/cart/services/cart_service.dart
new file mode 100644
--- /dev/null
+++ b/lib/features/cart/services/cart_service.dart
@@ -0,0 +1,15 @@
+import 'package:injectable/injectable.dart';
+
+@Singleton()
+class CartService {
+  final CartRepository _repository;
+
+  CartService(this._repository);
+
+  Future<void> addItem(CartItem item) async {
+    await _repository.addItem(item);
+  }
+
+  Future<List<CartItem>> getItems() async {
+    return _repository.getItems();
+  }
+}
diff --git a/lib/features/cart/model/cart_item.g.dart b/lib/features/cart/model/cart_item.g.dart
index 111..222 100644
--- a/lib/features/cart/model/cart_item.g.dart
+++ b/lib/features/cart/model/cart_item.g.dart
@@ -1,5 +1,7 @@
 // GENERATED CODE
+// new generated line 1
+// new generated line 2
"""


def test_parse_unified_diff_file_count():
    files = parse_unified_diff(SAMPLE_DIFF)
    assert len(files) == 3


def test_parse_unified_diff_paths():
    files = parse_unified_diff(SAMPLE_DIFF)
    paths = [f.path for f in files]
    assert "lib/features/cart/model/cart_item.dart" in paths
    assert "lib/features/cart/services/cart_service.dart" in paths
    assert "lib/features/cart/model/cart_item.g.dart" in paths


def test_parse_unified_diff_status():
    files = parse_unified_diff(SAMPLE_DIFF)
    by_path = {f.path: f for f in files}
    assert by_path["lib/features/cart/model/cart_item.dart"].status == "modified"
    assert by_path["lib/features/cart/services/cart_service.dart"].status == "added"


def test_parse_unified_diff_additions():
    files = parse_unified_diff(SAMPLE_DIFF)
    by_path = {f.path: f for f in files}
    cart_item = by_path["lib/features/cart/model/cart_item.dart"]
    assert cart_item.additions == 4  # price, sku, total getter, blank line
    assert cart_item.deletions == 0


def test_parse_unified_diff_new_file():
    files = parse_unified_diff(SAMPLE_DIFF)
    by_path = {f.path: f for f in files}
    service = by_path["lib/features/cart/services/cart_service.dart"]
    assert service.additions == 16
    assert service.status == "added"


def test_should_skip_file():
    assert should_skip_file("lib/features/cart/model/cart_item.g.dart") is True
    assert should_skip_file("lib/features/cart/model/cart_item.mocks.dart") is True
    assert should_skip_file("lib/injection.config.dart") is True
    assert should_skip_file("pubspec.lock") is True
    assert should_skip_file("lib/features/cart/model/cart_item.freezed.dart") is True
    assert should_skip_file("lib/features/cart/model/cart_item.dart") is False
    assert should_skip_file("lib/features/cart/services/cart_service.dart") is False


def test_extract_commit_log():
    log = "abc1234 fix cart state\ndef5678 add price field\n"
    commits = extract_commit_log(log)
    assert len(commits) == 2
    assert commits[0] == {"sha": "abc1234", "message": "fix cart state"}
    assert commits[1] == {"sha": "def5678", "message": "add price field"}


def test_extract_commit_log_empty():
    assert extract_commit_log("") == []
    assert extract_commit_log("   \n  ") == []


def test_get_diff_text_truncation():
    long_file = ChangedFile(
        path="test.dart",
        additions=500,
        diff_lines=["line"] * 500,
    )
    result = get_diff_text(long_file, max_lines=300)
    lines = result.split("\n")
    # 300 lines + truncation notice (may include blank line)
    assert len(lines) >= 301
    assert "TRUNCATED" in lines[-1]


def test_get_diff_text_no_truncation():
    short_file = ChangedFile(
        path="test.dart",
        additions=10,
        diff_lines=["line"] * 10,
    )
    result = get_diff_text(short_file, max_lines=300)
    assert "TRUNCATED" not in result


def test_order_files_for_review():
    files = [
        ChangedFile(path="lib/features/cart/widgets/item.dart"),
        ChangedFile(path="lib/features/cart/model/cart.dart"),
        ChangedFile(path="lib/features/cart/services/svc.dart"),
        ChangedFile(path="lib/features/cart/screens/main.dart"),
        ChangedFile(path="lib/features/cart/provider/state.dart"),
        ChangedFile(path="lib/features/cart/model/cart.g.dart"),  # generated — skipped
    ]
    ordered = order_files_for_review(files)
    paths = [f.path for f in ordered]

    # Generated file should be excluded
    assert "lib/features/cart/model/cart.g.dart" not in paths

    # Model before service before provider before screen before widget
    model_idx = paths.index("lib/features/cart/model/cart.dart")
    svc_idx = paths.index("lib/features/cart/services/svc.dart")
    provider_idx = paths.index("lib/features/cart/provider/state.dart")
    screen_idx = paths.index("lib/features/cart/screens/main.dart")
    widget_idx = paths.index("lib/features/cart/widgets/item.dart")

    assert model_idx < svc_idx < provider_idx < screen_idx < widget_idx


def test_parse_empty_diff():
    files = parse_unified_diff("")
    assert files == []


def test_parse_diff_with_renames():
    diff = """\
diff --git a/old_path.dart b/new_path.dart
rename from old_path.dart
rename to new_path.dart
"""
    files = parse_unified_diff(diff)
    assert len(files) == 1
    assert files[0].status == "renamed"
    assert files[0].path == "new_path.dart"
