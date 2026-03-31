# PyProbe X-Ray TODO

## High Priority

### Pending
(none)

## Medium Priority

- [ ] Add xray for more iterators (filter, map, zip, reversed)
- [ ] Improve generator extraction (currently minimal)
- [ ] Add xray for method objects (bound methods)

## Low Priority

- [ ] Add xray for collections types (deque, OrderedDict, defaultdict, Counter)
- [ ] Add xray for datetime types
- [ ] Add xray for Decimal and Fraction

---

## Completed

### Session - Tests and Polish
- [x] Add tests for all new extractors (type, module, code, cell, exception, etc.) - 55 tests total
- [x] Polish existing extractors (error handling, edge cases, docs)
- [x] Add more exception types to dispatcher (FileNotFoundError, AssertionError, etc.)

### Previous Session - Extended Type Support
- [x] Add xray support for bool (True/False)
- [x] Add xray support for NoneType  
- [x] Add xray support for complex numbers
- [x] Add xray support for range objects
- [x] Add xray support for slice objects
- [x] Add xray support for bytearray
- [x] Add xray support for memoryview
- [x] Add xray support for function objects
- [x] Add xray for type objects
- [x] Add xray for module objects
- [x] Add xray for code objects
- [x] Add xray for cell objects
- [x] Add xray for exceptions (BaseException + common subclasses)
- [x] Add xray for descriptor types (property, staticmethod, classmethod)
- [x] Add xray for builtin_function_or_method
- [x] Add xray for generator objects (basic)
- [x] Add xray for enumerate
- [x] Add tests for basic new types (test_extended_types.py - 22 tests)
- [x] Register all extractors in dispatcher
- [x] Update container list for recursive types

## Cancelled

- [ ] ~~Add xray for custom class instances (__dict__)~~ - Python 3.11+ uses managed dicts (PEP 659)

---

## Type Support Summary

| Type | Status | Notes |
|------|--------|-------|
| int | ✅ | Multi-precision support |
| float | ✅ | IEEE 754 |
| complex | ✅ | real + imag |
| str | ✅ | ASCII, Latin-1, UCS-2, UCS-4 |
| bytes | ✅ | |
| bytearray | ✅ | |
| memoryview | ✅ | Returns bytes |
| bool | ✅ | |
| NoneType | ✅ | |
| list | ✅ | Recursive |
| tuple | ✅ | Recursive |
| dict | ✅ | Unicode + General keys |
| set | ✅ | |
| frozenset | ✅ | |
| range | ✅ | |
| slice | ✅ | |
| function | ✅ | Returns metadata dict |
| type | ✅ | Returns name |
| module | ✅ | Returns name, dict keys |
| code | ✅ | Returns name, filename, consts |
| cell | ✅ | Returns contents |
| Exception* | ✅ | All common exception types |
| property | ✅ | fget, fset, fdel |
| staticmethod | ✅ | __func__ |
| classmethod | ✅ | __func__ |
| builtin_function | ✅ | __name__ |
| generator | ⚠️ | Basic support |
| enumerate | ✅ | start_index |
| filter | ❌ | |
| map | ❌ | |
| zip | ❌ | |
| reversed | ❌ | |
| collections.* | ❌ | |
| datetime.* | ❌ | |
| Custom instances | ❌ | Managed dicts issue |

---

## Memory Layouts Reference

```
Exception (BaseException):
  +24: args (tuple)

Type Object:
  +24: tp_name (char*)

Module Object:
  +16: md_dict (__dict__)

Code Object:
  +24: co_consts
  +112: co_filename
  +120: co_name

Cell Object:
  +16: ob_ref (cell_contents)

Property:
  +16: fget, +24: fset, +32: fdel, +40: doc

staticmethod/classmethod:
  +16: callable

enumerate:
  +16: en_index (Py_ssize_t)

builtin_function_or_method:
  +16: m_ml -> ml_name at offset 0
```
