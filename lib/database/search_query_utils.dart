// ===========================================================================
// file: lib/database/search_query_utils.dart
// purpose: Shared LIKE search utilities for drift DAOs.
//
// drift's built-in like() method generates "column LIKE ?" but does NOT
// support the ESCAPE clause. SQLite requires an explicit ESCAPE clause
// for escape characters to be interpreted in LIKE patterns.
//
// This file provides:
//   - LIKE wildcard escaping (%, _) using '!' as escape character
//   - A custom drift Expression that generates "column LIKE ? ESCAPE '!'"
//
// See: ADR-0013 (Search + Memory Recall Architecture)
//      https://www.sqlite.org/lang_expr.html#the_like_glob_regexp_match_and_extract_operators
// ===========================================================================

import 'package:drift/drift.dart';

/// Escape LIKE wildcard characters in a search query.
///
/// Uses `!` as the escape character (not backslash, which has its own
/// escaping complexities). Escapes the escape character itself first,
/// then the LIKE wildcards.
///
/// Must be used with [LikeWithEscape] to generate the matching ESCAPE clause.
String escapeLikeWildcards(String input) {
  return input
      .replaceAll('!', '!!')
      .replaceAll('%', '!%')
      .replaceAll('_', '!_');
}

/// A LIKE expression with an ESCAPE clause for drift.
///
/// Generates SQL: `column LIKE ? ESCAPE '!'`
///
/// drift's built-in `like()` generates `column LIKE ?` without ESCAPE,
/// which means escape characters in the pattern are treated as literals
/// by SQLite rather than escape prefixes. This custom expression adds
/// the required ESCAPE clause.
class LikeWithEscape extends Expression<bool> {
  /// The column expression to match against.
  final Expression<String> column;

  /// The LIKE pattern (should be pre-escaped via [escapeLikeWildcards]).
  final Variable<String> _pattern;

  /// Create a LIKE expression with ESCAPE clause.
  ///
  /// [column] — the drift column expression to search.
  /// [pattern] — the LIKE pattern, pre-escaped via [escapeLikeWildcards].
  LikeWithEscape(this.column, String pattern)
    : _pattern = Variable<String>(pattern);

  @override
  void writeInto(GenerationContext context) {
    column.writeInto(context);
    context.buffer.write(' LIKE ');
    _pattern.writeInto(context);
    context.buffer.write(" ESCAPE '!'");
  }
}
