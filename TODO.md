# TODO: Integrate Scalpel mutation capabilities into PyProbe class

## High Priority
- [x] Add mutation methods to PyProbe class in engine.py that delegate to Scalpel functions
- [x] Add mutate_int, mutate_float, safe_list_swap, safe_dict_value_swap methods to PyProbe class
- [x] Test that PyProbe instance can perform mutations directly

## Medium Priority
- [x] Ensure mutation methods use proper safety checks via Scalpel.assert_safe (already done by Scalpel)
- [x] Verify existing functionality still works after adding mutation exercises (address_test.py passes)
- [x] Test live_address_test.py to ensure concurrent scenarios work

## Low Priority
- [x] Consider adding batch mutation methods
- [x] Add documentation/examples for mutation usage
