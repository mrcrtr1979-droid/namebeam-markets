#!/usr/bin/env python3
"""Selftest: a share with a zero denominator prints n/a and never raises. Usage: python3 -I tools/data-truth/test_pct_share.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import regen_samples as rs

bad = 0


def chk(name, got, want):
    global bad
    ok = got == want
    bad += not ok
    print('%s  %s: got %r, want %r' % ('GREEN' if ok else 'RED  ', name, got, want))


try:
    chk('1 of 4 is 25.0%', rs.pct_share(1, 4), '25.0%')
    chk('0 of 0 is n/a (no ZeroDivisionError)', rs.pct_share(0, 0), 'n/a')
    chk('3 of 0 is n/a', rs.pct_share(3, 0), 'n/a')
except AttributeError as e:
    bad += 1
    print('RED   pct_share is not defined in regen_samples (%s)' % e)
print('RESULT', 'ALL GREEN' if not bad else '%d RED' % bad)
sys.exit(1 if bad else 0)
