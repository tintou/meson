# Meson Documentation

## Build dependencies

Meson uses itself and [Sphinx](https://www.sphinx-doc.org/) for generating documentation.

Install the required Python packages:
```
$ pip install sphinx myst-parser pydata-sphinx-theme chevron strictyaml
```

## Building the documentation

From the Meson repository root dir:
```
$ cd docs/
$ meson setup _build/
$ ninja -C _build/
```
Now you should be able to open the documentation locally:
```
_build/Meson documentation-doc/html/index.html
```

## Upload

The upload target clones the `documentation` branch of the meson repository,
replaces its content with the freshly built HTML, commits, and pushes.

```
$ ninja -C _build/ upload
```

On CI, this step runs automatically when changes are pushed to the `master` branch.
