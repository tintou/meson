project('test2', 'c', meson_version: '>=1.9.0')
pkg = import('pkgconfig')

test2_lib = library(
    'test2',
    'test2.c',
)

test2_dep = declare_dependency(
    link_with: test2_lib,
    include_directories: include_directories('.')
)

pkg.generate(test2_lib)

meson.override_dependency('test2', test2_dep)
