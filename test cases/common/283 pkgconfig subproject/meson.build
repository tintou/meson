project('test1', 'c', meson_version: '>=1.9.0')
pkg = import('pkgconfig')

test2_dep = dependency('test2')

test1_lib = library('test1',
    'test1.c',
    dependencies: [test2_dep]
)

pkg.generate(test1_lib,
requires: test2_dep,
)
