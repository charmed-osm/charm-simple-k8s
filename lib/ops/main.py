#!/usr/bin/env python3
# Copyright 2019 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
from pathlib import Path

import yaml

import ops.charm
import ops.framework
import ops.model

CHARM_STATE_FILE = '.unit-state.db'


def debugf(format, *args, **kwargs):
    pass


def _get_charm_dir():
    charm_dir = os.environ.get("JUJU_CHARM_DIR")
    if charm_dir is None:
        # Assume $JUJU_CHARM_DIR/lib/op/main.py structure.
        charm_dir = Path(f'{__file__}/../../..').resolve()
    else:
        charm_dir = Path(charm_dir).resolve()
    return charm_dir


def _load_metadata(charm_dir):
    metadata = yaml.safe_load((charm_dir / 'metadata.yaml').read_text())

    actions_meta = charm_dir / 'actions.yaml'
    if actions_meta.exists():
        actions_metadata = yaml.safe_load(actions_meta.read_text())
    else:
        actions_metadata = {}
    return metadata, actions_metadata


def _create_event_link(charm, bound_event):
    """Create a symlink for a particular event.

    charm -- A charm object.
    bound_event -- An event for which to create a symlink.
    """
    if issubclass(bound_event.event_type, ops.charm.HookEvent):
        event_dir = charm.framework.charm_dir / 'hooks'
        event_path = event_dir / bound_event.event_kind.replace('_', '-')
    elif issubclass(bound_event.event_type, ops.charm.ActionEvent):
        if not bound_event.event_kind.endswith("_action"):
            raise RuntimeError(f"action event name {bound_event.event_kind} needs _action suffix")
        event_dir = charm.framework.charm_dir / 'actions'
        # The event_kind is suffixed with "_action" while the executable is not.
        event_path = event_dir / bound_event.event_kind[:-len('_action')].replace('_', '-')
    else:
        raise RuntimeError(f'cannot create a symlink: unsupported event type {bound_event.event_type}')

    event_dir.mkdir(exist_ok=True)
    if not event_path.exists():
        # CPython has different implementations for populating sys.argv[0] for Linux and Windows. For Windows
        # it is always an absolute path (any symlinks are resolved) while for Linux it can be a relative path.
        target_path = os.path.relpath(os.path.realpath(sys.argv[0]), event_dir)

        # Ignore the non-symlink files or directories assuming the charm author knows what they are doing.
        debugf(f'Creating a new relative symlink at {event_path} pointing to {target_path}')
        event_path.symlink_to(target_path)


def _setup_event_links(charm_dir, charm):
    """Set up links for supported events that originate from Juju.

    Whether a charm can handle an event or not can be determined by
    introspecting which events are defined on it.

    Hooks or actions are created as symlinks to the charm code file which is determined by inspecting
    symlinks provided by the charm author at hooks/install or hooks/start.

    charm_dir -- A root directory of the charm.
    charm -- An instance of the Charm class.
    """
    for bound_event in charm.on.events().values():
        # Only events that originate from Juju need symlinks.
        if issubclass(bound_event.event_type, (ops.charm.HookEvent, ops.charm.ActionEvent)):
            _create_event_link(charm, bound_event)


def _emit_charm_event(charm, event_name):
    """Emits a charm event based on a Juju event name.

    charm -- A charm instance to emit an event from.
    event_name -- A Juju event name to emit on a charm.
    """
    event_to_emit = None
    try:
        event_to_emit = getattr(charm.on, event_name)
    except AttributeError:
        debugf(f"event {event_name} not defined for {charm}")

    # If the event is not supported by the charm implementation, do
    # not error out or try to emit it. This is to support rollbacks.
    if event_to_emit is not None:
        args, kwargs = _get_event_args(charm, event_to_emit)
        debugf(f'Emitting Juju event {event_name}')
        event_to_emit.emit(*args, **kwargs)


def _get_event_args(charm, bound_event):
    event_type = bound_event.event_type
    model = charm.framework.model

    if issubclass(event_type, ops.charm.RelationEvent):
        relation_name = os.environ['JUJU_RELATION']
        relation_id = int(os.environ['JUJU_RELATION_ID'].split(':')[-1])
        relation = model.get_relation(relation_name, relation_id)
    else:
        relation = None

    remote_app_name = os.environ.get('JUJU_REMOTE_APP', '')
    remote_unit_name = os.environ.get('JUJU_REMOTE_UNIT', '')
    if remote_app_name or remote_unit_name:
        if not remote_app_name:
            if '/' not in remote_unit_name:
                raise RuntimeError(f'invalid remote unit name: {remote_unit_name}')
            remote_app_name = remote_unit_name.split('/')[0]
        args = [relation, model.get_app(remote_app_name)]
        if remote_unit_name:
            args.append(model.get_unit(remote_unit_name))
        return args, {}
    elif relation:
        return [relation], {}
    return [], {}


def main(charm_class):
    """Setup the charm and dispatch the observed event.

    The event name is based on the way this executable was called (argv[0]).
    """

    charm_dir = _get_charm_dir()

    # Process the Juju event relevant to the current hook execution
    # JUJU_HOOK_NAME, JUJU_FUNCTION_NAME, and JUJU_ACTION_NAME are not used
    # in order to support simulation of events from debugging sessions.
    # TODO: For Windows, when symlinks are used, this is not a valid method of getting an event name (see LP: #1854505).
    juju_exec_path = Path(sys.argv[0])
    juju_event_name = juju_exec_path.name.replace('-', '_')
    if juju_exec_path.parent.name == 'actions':
        juju_event_name = f'{juju_event_name}_action'

    metadata, actions_metadata = _load_metadata(charm_dir)
    meta = ops.charm.CharmMeta(metadata, actions_metadata)
    unit_name = os.environ['JUJU_UNIT_NAME']
    model = ops.model.Model(unit_name, meta, ops.model.ModelBackend())

    # TODO: If Juju unit agent crashes after exit(0) from the charm code
    # the framework will commit the snapshot but Juju will not commit its
    # operation.
    charm_state_path = charm_dir / CHARM_STATE_FILE
    framework = ops.framework.Framework(charm_state_path, charm_dir, meta, model)
    try:
        charm = charm_class(framework, None)

        # When a charm is force-upgraded and a unit is in an error state Juju does not run upgrade-charm and
        # instead runs the failed hook followed by config-changed. Given the nature of force-upgrading
        # the hook setup code is not triggered on config-changed.
        # 'start' event is included as Juju does not fire the install event for K8s charms (see LP: #1854635).
        if juju_event_name in ('install', 'start', 'upgrade_charm') or juju_event_name.endswith('_storage_attached'):
            _setup_event_links(charm_dir, charm)

        framework.reemit()

        _emit_charm_event(charm, juju_event_name)

        framework.commit()
    finally:
        framework.close()
