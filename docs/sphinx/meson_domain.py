from __future__ import annotations

import json
from pathlib import Path
import typing as T

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.builders import Builder
from sphinx.domains import Domain, ObjType
from sphinx.environment import BuildEnvironment
from sphinx.roles import XRefRole
from sphinx.util import logging
from sphinx.util.docutils import SphinxRole
from sphinx.util.nodes import make_refnode

logger = logging.getLogger(__name__)


_SINCE_CLASSES = (
    'd-inline-flex mb-1 px-1 fw-semibold small text-nowrap '
    'text-success-emphasis bg-success-subtle '
    'border border-success-subtle rounded-2'
)

_DEPRECATED_CLASSES = (
    'd-inline-flex mb-1 px-1 fw-semibold small text-nowrap '
    'text-warning-emphasis bg-warning-subtle '
    'border border-warning-subtle rounded-2'
)

_OPTIONAL_CLASSES = (
    'd-inline-flex mb-1 px-1 fw-semibold small text-nowrap '
    'text-secondary-emphasis bg-secondary-subtle '
    'border border-secondary-subtle rounded-2'
)


class MesonSinceRole(SphinxRole):
    """Renders :meson:since:`x.y.z` as a styled Bootstrap badge."""

    def run(self) -> T.Tuple[T.List[nodes.Node], T.List[nodes.system_message]]:
        html = f'<span class="{_SINCE_CLASSES}">Since {self.text}</span>'
        return [nodes.raw('', html, format='html')], []


class MesonDeprecatedRole(SphinxRole):
    """Renders :meson:deprecated:`x.y.z` as a styled Bootstrap badge."""

    def run(self) -> T.Tuple[T.List[nodes.Node], T.List[nodes.system_message]]:
        html = f'<span class="{_DEPRECATED_CLASSES}">Deprecated since {self.text}</span>'
        return [nodes.raw('', html, format='html')], []


class MesonOptionalRole(SphinxRole):
    """Renders :meson:optional:`` as a styled Bootstrap badge."""

    def run(self) -> T.Tuple[T.List[nodes.Node], T.List[nodes.system_message]]:
        html = f'<span class="{_OPTIONAL_CLASSES}">optional</span>'
        return [nodes.raw('', html, format='html')], []



class MesonXRefRole(XRefRole):
    """Cross-reference role that appends () to function and method names."""

    def process_link(
        self,
        env: BuildEnvironment,
        refnode: nodes.Element,
        has_explicit_title: bool,
        title: str,
        target: str,
    ) -> T.Tuple[str, str]:
        if not has_explicit_title and refnode['reftype'] in ('func', 'meth'):
            title += '()'
        return title, target


class MesonDomain(Domain):
    name = 'meson'
    label = 'Meson'

    object_types: T.Dict[str, ObjType] = {
        'function': ObjType('function', 'func', 'obj'),
        'method':   ObjType('method',   'meth', 'obj'),
        'object':   ObjType('object',   'obj'),
    }

    roles = {
        'func':       MesonXRefRole(),
        'meth':       MesonXRefRole(),
        'obj':        MesonXRefRole(),
        'since':      MesonSinceRole(),
        'deprecated': MesonDeprecatedRole(),
        'optional':   MesonOptionalRole(),
    }

    directives: T.Dict[str, T.Any] = {}

    initial_data: T.Dict[str, T.Any] = {
        'objects': {},  # name -> {'docname': str, 'anchor': str, 'type': str}
    }

    @property
    def objects(self) -> T.Dict[str, T.Dict[str, str]]:
        return self.data.setdefault('objects', {})

    def load_from_refman(self, refman_json: T.Dict[str, str]) -> None:
        """Populate the domain from refman_links.json."""
        self.objects.clear()
        for key, url in refman_json.items():
            page, _, anchor = url.partition('#')
            docname = page.removesuffix('.html')

            if key.startswith('@'):
                obj_type = 'object'
                name = key[1:]
            elif '.' in key:
                obj_type = 'method'
                name = key
            else:
                obj_type = 'function'
                name = key

            self.objects[name] = {
                'docname': docname,
                'anchor': anchor,
                'type': obj_type,
            }

    def resolve_xref(
        self,
        env: BuildEnvironment,
        fromdocname: str,
        builder: Builder,
        typ: str,
        target: str,
        node: addnodes.pending_xref,
        contnode: nodes.Element,
    ) -> T.Optional[nodes.Element]:
        if target not in self.objects:
            return None
        obj = self.objects[target]
        return make_refnode(
            builder,
            fromdocname,
            obj['docname'],
            obj['anchor'] or None,
            contnode,
            target,
        )

    def resolve_any_xref(
        self,
        env: BuildEnvironment,
        fromdocname: str,
        builder: Builder,
        target: str,
        node: addnodes.pending_xref,
        contnode: nodes.Element,
    ) -> T.List[T.Tuple[str, nodes.Element]]:
        if target not in self.objects:
            return []
        obj = self.objects[target]
        ref = make_refnode(
            builder,
            fromdocname,
            obj['docname'],
            obj['anchor'] or None,
            contnode,
            target,
        )
        return [(f'meson:{obj["type"]}', ref)]

    def get_objects(self) -> T.Iterator[T.Tuple[str, str, str, str, str, int]]:
        for name, obj in self.objects.items():
            dispname = name + '()' if obj['type'] in ('function', 'method') else name
            yield (name, dispname, obj['type'], obj['docname'], obj['anchor'], 1)


def _load_domain_data(app: Sphinx) -> None:
    data_file: T.Optional[str] = app.config.refman_data_file
    if not data_file:
        return

    path = Path(data_file)
    if not path.is_absolute():
        path = Path(app.confdir) / path

    if not path.exists():
        logger.warning('Meson domain: refman_data_file %s not found', path)
        return

    raw: T.Dict[str, str] = json.loads(path.read_text(encoding='utf-8'))
    domain: MesonDomain = app.env.get_domain('meson')  # type: ignore[assignment]
    domain.load_from_refman(raw)
    logger.info('Meson domain: registered %d objects', len(raw))


def setup(app: Sphinx) -> T.Dict[str, T.Any]:
    app.add_domain(MesonDomain)
    app.connect('builder-inited', _load_domain_data)

    return {
        'version': '1.0',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
