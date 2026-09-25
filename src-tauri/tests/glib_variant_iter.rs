#![cfg(target_os = "linux")]
use glib::{variant::ToVariant, Variant};

// Exercise every iterator entrypoint listed in RUSTSEC-2024-0429 with
// optimization enabled. These calls share the corrected C out-parameter.
#[test]
fn string_variant_iterator_preserves_values_in_both_directions() {
    let strings = ["", "one", "日本語", "café", "last"];
    let variant = Variant::array_from_iter::<String>(strings.iter().map(|s| s.to_variant()));
    assert_eq!(variant.array_iter_str().unwrap().collect::<Vec<_>>(), strings);
    assert_eq!(variant.array_iter_str().unwrap().rev().collect::<Vec<_>>(),
               strings.iter().copied().rev().collect::<Vec<_>>());
    assert_eq!(variant.array_iter_str().unwrap().last(), Some("last"));
    let mut iter = variant.array_iter_str().unwrap();
    assert_eq!(iter.next(), Some(""));
    assert_eq!(iter.next_back(), Some("last"));
    assert_eq!(iter.nth(1), Some("日本語"));
    assert_eq!(iter.nth_back(0), Some("café"));
    assert_eq!(iter.next(), None);
    assert_eq!(iter.next_back(), None);
}

#[test]
fn string_variant_iterator_handles_empty_and_exhausted_arrays() {
    let empty = Variant::array_from_iter::<String>(std::iter::empty::<Variant>());
    let mut iter = empty.array_iter_str().unwrap();
    assert_eq!(iter.next(), None);
    assert_eq!(iter.next_back(), None);
    assert_eq!(iter.last(), None);
    let one = ["only"].to_variant();
    assert_eq!(one.array_iter_str().unwrap().nth(1), None);
    assert_eq!(one.array_iter_str().unwrap().nth_back(1), None);
}
