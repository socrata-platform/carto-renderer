"""
A file just to hold the version number, allows automated version increasing.
"""

SEMANTIC = '0.1.8-SNAPSHOT'
BUILD_TIME = 'UNKNOWN'
try:
    with open('build-time.txt') as f:
        CONTENTS = f.readline().rstrip()
        if CONTENTS:
            BUILD_TIME = CONTENTS
except IOError:
    pass
