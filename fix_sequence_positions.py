#!/usr/bin/env python3
"""
Script to fix sequencePosition values in TTL files.

For LessonInclusions within a UnitVariant:
- Renumbers so they start at 1 and are consecutive
- E.g., 2,3,4 becomes 1,2,3 and 1,2,3,6,7,8 becomes 1,2,3,4,5,6

Also checks UnitVariantInclusions within Programmes to verify they
start at 1 and are consecutive.
"""

import re
import glob
from pathlib import Path
from collections import defaultdict


def parse_ttl_file(filepath):
    """Parse a TTL file and extract relevant data."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    return content


def find_lesson_inclusion_issues(content):
    """
    Find LessonInclusions grouped by UnitVariant and identify issues.

    Returns:
        dict: mapping from unitvariant_id to dict with 'inclusions' list and 'needs_fix' bool
    """
    # Group lesson inclusions by unit variant using the inclusion ID pattern
    unitvariant_inclusions = defaultdict(list)

    # Find all LessonInclusion definitions
    lesson_inclusion_pattern = re.compile(
        r'oakcurric:(inclusion-unitvariant-(\d+)-lesson-(\d+))\s+'
        r'a curric:LessonInclusion\s*;\s+'
        r'curric:includesLesson\s+oakcurric:lesson-\d+\s*;\s+'
        r'curric:sequencePosition\s+"(\d+)"\^\^xsd:positiveInteger',
        re.MULTILINE
    )

    for match in lesson_inclusion_pattern.finditer(content):
        inclusion_id = match.group(1)
        unitvariant_id = match.group(2)
        lesson_id = match.group(3)
        seq_pos = int(match.group(4))

        unitvariant_inclusions[unitvariant_id].append({
            'inclusion_id': inclusion_id,
            'lesson_id': lesson_id,
            'sequence_position': seq_pos
        })

    issues = {}
    for uv_id, inclusions in unitvariant_inclusions.items():
        # Sort by sequence position
        sorted_inclusions = sorted(inclusions, key=lambda x: x['sequence_position'])
        positions = [inc['sequence_position'] for inc in sorted_inclusions]

        # Check if starts at 1 and is consecutive
        expected = list(range(1, len(positions) + 1))
        needs_fix = positions != expected

        issues[uv_id] = {
            'inclusions': sorted_inclusions,
            'current_positions': positions,
            'expected_positions': expected,
            'needs_fix': needs_fix
        }

    return issues


def fix_lesson_inclusions(content, issues):
    """
    Fix the sequencePosition values for LessonInclusions that need fixing.

    Returns:
        str: modified content
        int: number of fixes made
    """
    fixes_made = 0
    new_content = content

    for uv_id, data in issues.items():
        if not data['needs_fix']:
            continue

        sorted_inclusions = data['inclusions']
        for new_pos, inclusion in enumerate(sorted_inclusions, 1):
            old_pos = inclusion['sequence_position']
            if old_pos != new_pos:
                inclusion_id = inclusion['inclusion_id']
                # Find and replace the sequencePosition
                old_pattern = re.compile(
                    rf'(oakcurric:{re.escape(inclusion_id)}\s+'
                    rf'a curric:LessonInclusion\s*;\s+'
                    rf'curric:includesLesson\s+oakcurric:lesson-\d+\s*;\s+'
                    rf'curric:sequencePosition\s+)"{old_pos}"\^\^xsd:positiveInteger'
                )
                new_content = old_pattern.sub(
                    rf'\g<1>"{new_pos}"^^xsd:positiveInteger',
                    new_content
                )
                fixes_made += 1

    return new_content, fixes_made


def find_unit_variant_inclusion_issues(content):
    """
    Find UnitVariantInclusions grouped by Programme and identify issues.

    Returns:
        dict: mapping from programme_id to check results
    """
    # Group UnitVariantInclusions by programme using the inclusion ID pattern
    programme_inclusions = defaultdict(list)

    # Match inclusion IDs like: inclusion-programme-biology-year-group-10-higher-ocr-pos-1
    # The programme ID is everything between 'inclusion-' and '-pos-N'
    uv_inclusion_pattern = re.compile(
        r'oakcurric:(inclusion-(programme-[a-zA-Z0-9-]+)-pos-(\d+))\s+'
        r'a curric:UnitVariantInclusion\s*;\s+'
        r'curric:includesUnitVariant\s+oakcurric:unitvariant-(\d+)\s*;\s+'
        r'curric:sequencePosition\s+"(\d+)"\^\^xsd:positiveInteger',
        re.MULTILINE
    )

    for match in uv_inclusion_pattern.finditer(content):
        inclusion_id = match.group(1)
        programme_id = match.group(2)
        pos_in_name = int(match.group(3))
        unitvariant_id = match.group(4)
        seq_pos = int(match.group(5))

        programme_inclusions[programme_id].append({
            'inclusion_id': inclusion_id,
            'unitvariant_id': unitvariant_id,
            'pos_in_name': pos_in_name,
            'sequence_position': seq_pos
        })

    results = {}
    for prog_id, inclusions in programme_inclusions.items():
        # Sort by sequence position
        sorted_inclusions = sorted(inclusions, key=lambda x: x['sequence_position'])
        positions = [inc['sequence_position'] for inc in sorted_inclusions]

        # Check if starts at 1 and is consecutive
        expected = list(range(1, len(positions) + 1))
        is_valid = positions == expected

        results[prog_id] = {
            'inclusions': sorted_inclusions,
            'current_positions': positions,
            'expected_positions': expected,
            'is_valid': is_valid
        }

    return results


def fix_unit_variant_inclusions(content, issues):
    """
    Fix the sequencePosition values for UnitVariantInclusions that need fixing.

    Returns:
        str: modified content
        int: number of fixes made
    """
    fixes_made = 0
    new_content = content

    for prog_id, data in issues.items():
        if data['is_valid']:
            continue

        sorted_inclusions = data['inclusions']
        for new_pos, inclusion in enumerate(sorted_inclusions, 1):
            old_pos = inclusion['sequence_position']
            if old_pos != new_pos:
                inclusion_id = inclusion['inclusion_id']
                # Find and replace the sequencePosition
                old_pattern = re.compile(
                    rf'(oakcurric:{re.escape(inclusion_id)}\s+'
                    rf'a curric:UnitVariantInclusion\s*;\s+'
                    rf'curric:includesUnitVariant\s+oakcurric:unitvariant-\d+\s*;\s+'
                    rf'curric:sequencePosition\s+)"{old_pos}"\^\^xsd:positiveInteger'
                )
                new_content = old_pattern.sub(
                    rf'\g<1>"{new_pos}"^^xsd:positiveInteger',
                    new_content
                )
                fixes_made += 1

    return new_content, fixes_made


def process_file(filepath, fix=True, fix_uv_inclusions=False):
    """Process a single TTL file."""
    print(f"\n{'='*70}")
    print(f"Processing: {filepath}")
    print('='*70)

    content = parse_ttl_file(filepath)
    file_modified = False

    # Check and fix LessonInclusions
    lesson_issues = find_lesson_inclusion_issues(content)

    uv_with_issues = [uv_id for uv_id, data in lesson_issues.items() if data['needs_fix']]

    if uv_with_issues:
        print(f"\nLessonInclusion issues found for {len(uv_with_issues)} UnitVariants:")
        for uv_id in uv_with_issues[:10]:  # Show first 10
            data = lesson_issues[uv_id]
            print(f"  unitvariant-{uv_id}: {data['current_positions']} -> {data['expected_positions']}")
        if len(uv_with_issues) > 10:
            print(f"  ... and {len(uv_with_issues) - 10} more")

        if fix:
            new_content, fixes_made = fix_lesson_inclusions(content, lesson_issues)
            if fixes_made > 0:
                content = new_content
                file_modified = True
                print(f"\nFixed {fixes_made} LessonInclusion sequencePosition values")
    else:
        print("\nNo LessonInclusion issues found")

    # Check UnitVariantInclusions
    uv_inclusion_issues = find_unit_variant_inclusion_issues(content)

    invalid_programmes = [prog_id for prog_id, data in uv_inclusion_issues.items() if not data['is_valid']]

    if invalid_programmes:
        print(f"\nUnitVariantInclusion issues found for {len(invalid_programmes)} Programmes:")
        for prog_id in invalid_programmes[:10]:
            data = uv_inclusion_issues[prog_id]
            print(f"  {prog_id}: {data['current_positions']} (expected: {data['expected_positions']})")
        if len(invalid_programmes) > 10:
            print(f"  ... and {len(invalid_programmes) - 10} more")

        if fix_uv_inclusions:
            new_content, fixes_made = fix_unit_variant_inclusions(content, uv_inclusion_issues)
            if fixes_made > 0:
                content = new_content
                file_modified = True
                print(f"\nFixed {fixes_made} UnitVariantInclusion sequencePosition values")
    else:
        print(f"\nAll {len(uv_inclusion_issues)} Programmes have valid UnitVariantInclusion sequences")

    # Write the file if modified
    if file_modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)

    return {
        'lesson_inclusion_issues': len(uv_with_issues),
        'programme_issues': len(invalid_programmes),
        'unitvariants_checked': len(lesson_issues),
        'programmes_checked': len(uv_inclusion_issues)
    }


def main():
    """Main function."""
    import sys

    fix = '--check-only' not in sys.argv
    fix_uv_inclusions = '--fix-uv-inclusions' in sys.argv

    # Find all key-stage TTL files
    pattern = 'data/subjects/**/*-key-stage-*.ttl'
    files = glob.glob(pattern, recursive=True)

    if not files:
        print(f"No files found matching pattern: {pattern}")
        return

    print(f"Found {len(files)} files to process")

    if fix:
        print("Mode: FIX LessonInclusions (will modify files)")
        if fix_uv_inclusions:
            print("      Also fixing UnitVariantInclusions")
    else:
        print("Mode: CHECK ONLY (no modifications)")

    total_stats = {
        'files_processed': 0,
        'files_with_lesson_issues': 0,
        'files_with_programme_issues': 0,
        'total_unitvariants_checked': 0,
        'total_programmes_checked': 0
    }

    for filepath in sorted(files):
        stats = process_file(filepath, fix=fix, fix_uv_inclusions=fix_uv_inclusions)
        total_stats['files_processed'] += 1
        if stats['lesson_inclusion_issues'] > 0:
            total_stats['files_with_lesson_issues'] += 1
        if stats['programme_issues'] > 0:
            total_stats['files_with_programme_issues'] += 1
        total_stats['total_unitvariants_checked'] += stats['unitvariants_checked']
        total_stats['total_programmes_checked'] += stats['programmes_checked']

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Files processed: {total_stats['files_processed']}")
    print(f"Files with LessonInclusion issues: {total_stats['files_with_lesson_issues']}")
    print(f"Files with UnitVariantInclusion issues: {total_stats['files_with_programme_issues']}")
    print(f"Total UnitVariants checked: {total_stats['total_unitvariants_checked']}")
    print(f"Total Programmes checked: {total_stats['total_programmes_checked']}")


if __name__ == '__main__':
    main()
