#!/usr/bin/env python
"""
Python script to duplicate the logic of sbt-release.
"""
import pytest
import sys
from os.path import abspath, dirname, join
from sh import git


def set_version(file_name, from_ver, to_ver):
    """
    Replaces from_ver with to_ver in file_name.
    """
    body = None
    with open(file_name, 'r') as ver_file:
        body = ver_file.read()

    with open(file_name, 'w') as ver_file:
        ver_file.write(body.replace(from_ver, to_ver))


def prompt(message, pattern, invalid, default):
    """
    Prompt for input, and validate the result.
    """
    import re

    result = None
    while not result:
        if sys.version_info[0] == 2:
            line = raw_input(message)  # pylint: disable=undefined-variable
        else:
            line = input(message)
        if line and not re.match(pattern, line):
            print(invalid)
        else:
            result = line if result else default

    return result


def main():
    """Script body"""
    app_dir = join(dirname(abspath(__file__)), '..')
    sys.path.append(app_dir)

    from carto_renderer import version  # pylint: disable=import-error

    cur_version = version.SEMANTIC
    if not cur_version.endswith('-SNAPSHOT'):
        raise ValueError('Not a SNAPSHOT version!')
    default_release = cur_version.replace('-SNAPSHOT', '')

    pytest.main(app_dir)

    release_version = prompt(
        'Release version [{ver}]: '.format(ver=default_release),
        r'^\d+[.]\d+[.]\d+$',
        'Release version should be Major.Minor.Patch!',
        default_release)

    split_version = [int(i) for i in release_version.split('.')]
    split_version[2] += 1
    default_next = '.'.join([str(s) for s in split_version]) + '-SNAPSHOT'

    next_version = prompt(
        'Next version[' + default_next + ']: ',
        r'^\d+[.]\d+[.]\d+-SNAPSHOT$',
        'Not a valid SNAPSHOT version!',
        default_next)

    ver_file = join(app_dir, 'carto_renderer', 'version.py')
    set_version(ver_file, cur_version, release_version)
    git.add(ver_file)

    git.commit('-m', 'Setting version to ' + release_version)
    git.tag('v' + release_version)

    set_version(ver_file, release_version, next_version)
    git.add(ver_file)
    git.commit('-m' 'Setting version to ' + next_version)

    do_push = prompt('Push changes to the remote repository (y/n)? [y]:',
                     '.*', None, 'y')

    if do_push.lower().startswith('y'):
        print(git.push())
        print(git.push('--tags'))

main()
