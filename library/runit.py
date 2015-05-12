#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import tempfile

DOCUMENTATION = '''
---
module: runit
version_added: "1.9.1"
short_description: Sets up a runit service
description:
    - As a role it installs runit. As a task it creates a new runit service
    service.
notes:
    - This module creates a simple run file and run log file for your service.
    - Note: the role runit must be executed before this task
    -
    - Due to the nature of runit, enabed='yes' will cause runit to start.
    - In the auto='yes' mode you must provide a command for the run file to execute when you
    - want your service to start and provide the user the running service will run under.
    - However, if you want more control, you can set  auto='no' and use the returned vars
    - of run_service_file and log_service_file and generate your own run files for both.
    - Note, that in the case of using your own run file, you'll need to run this module in the
    - enabled='false' state, then generate your files to the locations specified by the
    - run_service_file and log_service_file and then enable the service after the custom run
    - files have been place in their correct paths.
    - In the case of auto='no', the 'user' and 'command' values are not used.
    -
    - If the service is not enabled, state and action values are ignored.
requirements: [ ]
author: Franklin Wise
options:
  name:
    required: true
    default: ""
    description:
        - The name of the service, directories will be created with this name and this name
        will be used to start and stop the service. The name should consist of [A-Za-z0-9_-]
  state:
    required: true
    choices: [ "up", "down", "once" ]
    description:
	    Change the state of the service only if enabled='yes'
	    * up - Keep the service up, if it crashes or stops attempt to restart it.
	    * down - Bring the service down.
	    * once - Can only be run from the down state. Will start the service, however, will not restart if the service crashes.
  enabled:
    default: "yes"
    required: false
    choices: [ "yes", "no" ]
    description:
        - if enabled the service will be running and also will start on system boot
        if disabled the service will not be running and will not start on system boot
  timeout:
    default: 7
    required: false
    description:
        - The number of seconds to wait for the service to start or stop before timing out
  auto:
    required: false
    default: "yes"
    choices: [ "yes", "no" ]
    description:
	    - 'yes' Automatically creates the run_service_file and the log_service_file to execute the service.
	    requires the 'user' and 'command' values to be set
        - 'no' The caller is required to create the run file and the run log file.
        See the notes for a more detailed explanation.
  command:
    required: false
    default: null
    description:
        - The command to run that will start the executable to run. Required if auto='yes'
  user:
    required: false
    default: "root"
    description:
        - The user that the service will run under. It is recommended that this value be set if auto='yes'
  env_vars:
    required: false
    default: {}
    description:
        - A hash of key value pairs of environmental variables that should be available for the service
  action:
    required: false
    default: null
    choices: [ "restart", "reload" ]
    description:
      - if the service is up and enabled causes the given action to take place:
        * restart will stop the servie and the start it
        * reload will send the HUP signal to cause a config reload
'''

EXAMPLES = '''

# runit if enabled is in the running state
- runit: name=myservicename enabled=true state=running timeout=9

- runit: name=myservicename enabled=true state=running timeout=9 signal=HUP
'''

def get_status(module, name):
    sv = module.get_bin_path('sv', True)
    rc, out, err = module.run_command('%s status %s' % (sv, name), check_rc=False)
    # run: name: (pid 22222) 10s; run: log: (pid 33333) 10s
    for line in out.split('\n'):
        parts = line.lower().split()
        return rc, out, parts[0][:-1]
    else:
        return rc, out, ''

def run_command(module, command, name, timeout):
    sv = module.get_bin_path('sv', True)
    rc, out, err = module.run_command('%s -w %s %s %s' % (sv, str(timeout), command, name), check_rc=True)
    if rc != 0:
        return rc, out, 'error'
    else:
        return status()

def get_file_state(path):
    ''' Find out current state '''

    if os.path.lexists(path):
        if os.path.islink(path):
            return 'link'
        elif os.path.isdir(path):
            return 'directory'
        elif os.stat(path).st_nlink > 1:
            return 'hard'
        else:
            # could be many other things, but defaulting to file
            return 'file'

    return 'absent'

def directory(module, path, args):
    recurse = True
    file_args = args.copy()
    file_args['path'] = path
    changed = False
    prev_state = get_file_state(path)
    follow = True
    if follow and prev_state == 'link':
        path = os.path.realpath(path)
        prev_state = get_file_state(path)

    if prev_state == 'absent':
        if module.check_mode:
            module.exit_json(changed=True)
        changed = True
        curpath = ''
        # Split the path so we can apply filesystem attributes recursively
        # from the root (/) directory for absolute paths or the base path
        # of a relative path.  We can then walk the appropriate directory
        # path to apply attributes.
        for dirname in path.strip('/').split('/'):
            curpath = '/'.join([curpath, dirname])
            # Remove leading slash if we're creating a relative path
            if not os.path.isabs(path):
                curpath = curpath.lstrip('/')
            if not os.path.exists(curpath):
                os.mkdir(curpath)
                tmp_file_args = file_args.copy()
                tmp_file_args['path']=curpath
                changed = module.set_fs_attributes_if_different(tmp_file_args, changed)

    # We already know prev_state is not 'absent', therefore it exists in some form.
    elif prev_state != 'directory':
        module.fail_json(path=path, msg='%s already exists as a %s' % (path, prev_state))

    changed = module.set_fs_attributes_if_different(file_args, changed)

    if recurse:
        changed |= recursive_set_attributes(module, file_args['path'], follow, file_args)

    return changed

def write_file(module,lines,dest):

    tmpfd, tmpfile = tempfile.mkstemp()
    f = os.fdopen(tmpfd,'wb')
    f.writelines(lines)
    f.close()

    dest = os.path.realpath(os.path.expanduser(dest))
    new_sha = module.sha1(tmpfile)
    orig_sha = module.sha1(dest)

    if new_sha != orig_sha:
        module.atomic_move(tmpfile, dest)
        file_args = module.load_file_common_arguments(dict(path=dest))
        file_args['mode'] = 0755
        file_args['owner'] = 'root'
        file_args['group'] = 'root'
        module.set_fs_attributes_if_different(file_args, False)

        return True
    else:
        file_args = module.load_file_common_arguments(dict(path=dest))
        file_args['mode'] = 0755
        file_args['owner'] = 'root'
        file_args['group'] = 'root'
        return module.set_fs_attributes_if_different(file_args, False)


def recursive_set_attributes(module, path, follow, file_args):
    changed = False
    for root, dirs, files in os.walk(path):
        for fsobj in dirs + files:
            fsname = os.path.join(root, fsobj)
            if not os.path.islink(fsname):
                tmp_file_args = file_args.copy()
                tmp_file_args['path']=fsname
                changed |= module.set_fs_attributes_if_different(tmp_file_args, changed)
            else:
                tmp_file_args = file_args.copy()
                tmp_file_args['path']=fsname
                changed |= module.set_fs_attributes_if_different(tmp_file_args, changed)
                if follow:
                    fsname = os.path.join(root, os.readlink(fsname))
                    if os.path.isdir(fsname):
                        changed |= recursive_set_attributes(module, fsname, follow, file_args)
                    tmp_file_args = file_args.copy()
                    tmp_file_args['path']=fsname
                    changed |= module.set_fs_attributes_if_different(tmp_file_args, changed)
    return changed

def main():

    module = AnsibleModule(
        argument_spec = dict(
            name  = dict(required=True),
            state = dict(required=True, choices=['up','down','once'] ),
            enabled = dict(default='yes', type='bool'),
            timeout = dict(required=False, default=7),
            env_vars = dict(required=False, default=None),
            action = dict(required=False, choices=['restart','reload'], default=None),
            auto = dict(required=False, default='yes', type='bool'),
            command = dict(required=False, default=None),
            user = dict(required=False, default='root')
    #        signal = dict(required=False, choices=['HUP','CONT','TERM', 'KILL', 'USR1', 'USR2', 'STOP', 'ALRM', 'QUIT'], default=None),
    #        validate = dict(required=False, default=None),
        ),
        #add_file_common_args=True,
        supports_check_mode=True
    )

    params = module.params
    name  = params['name']
    state = params['state']
    enabled = params['enabled']
    timeout = params['timeout']
    env_vars = params['env_vars']
    action = params['action']
    auto = params['auto']
    command = params['command']
    user = params['user']
    #signal = params['signal']
    #validate = params['validate']
    #params['validate'] = path = os.path.expanduser(params['validate'])

    rc, message, status = get_status(module, name)
    is_running = 'run' == status
    is_down = 'down' == status
    #is_failed = 'fail' == status
    #is_warning = 'warning' == status

    service_dir = '/etc/sv/%s' % (name)
    service_log_dir = '/etc/sv/%s/log' % (name)
    service_env_dir = '/etc/sv/%s/env' % (name)

    changed = False

    service_dir_args = module.load_file_common_arguments(dict(path=service_dir))
    service_dir_args['mode'] = 0755

    if get_file_state(service_dir) != 'directory':
        changed |= directory(module, service_dir, service_dir_args)

    service_log_dir_args = module.load_file_common_arguments(dict(path=service_log_dir))
    service_log_dir_args['mode'] = 0755

    if get_file_state(service_log_dir) != 'directory':
        changed |= directory(module, service_log_dir, service_log_dir_args)

    service_env_dir_args = module.load_file_common_arguments(dict(path=service_log_dir))
    service_env_dir_args['mode'] = 0755

    if get_file_state(service_env_dir) != 'directory':
        changed |= directory(module, service_env_dir, service_env_dir_args)

    run_service_file = '%s/run' % (service_dir )
    log_service_file = '%s/run' % (service_log_dir )

    log_command = '''#!/bin/sh
exec chpst -u %s svlogd -tt /var/log/%s
    ''' % (user, name)

    command_text = '''#!/bin/sh
exec 2>&1
exec chpst -e /etc/sv/%s/env -u %s %s
    ''' % (name, user, command)

    if auto:
        # create run
        changed |= write_file(module, command_text, run_service_file)
        # create log/run
        changed |= write_file(module, log_command, log_service_file)

    # create each file for ENV
    if not env_vars is None:
        for k, v in env_vars.iteritems():
            changed |= write_file(module, contents,'%s/%s' % (service_env_dir, k ))

    enabled_service_dir = '/etc/service/%s' % name

    # could handle edge cases like if the service folder exists, but is not a symlink etc.
    enabled_state = get_file_state(enabled_service_dir)

    if enabled is None:
        pass

    elif enabled and enabled_state != 'link':
        if enabled_state == 'absent':
            try:
                os.symlink(service_dir + '/', enabled_service_dir)
                is_running=True #dont trigger an up since we just started
            except OSError as e:
                module.fail_json(path=enabled_service_dir, msg='Error while linking: %s' % str(e))
        else:
            module.fail_json(path=enabled_service_dir, msg="symlinking failed - can not overwrite existing %s " % enabled_state)
    elif not enabled and enabled_state != 'absent':
        if enabled_state == 'link':
            try:
                os.unlink(enabled_service_dir)
            except Exception as e:
                module.fail_json(path=enabled_service_dir, msg="unlinking failed: %s " % str(e))
        elif enabled_state != 'absent':
            module.fail_json(path=enabled_service_dir, msg="unsymlinking failed - existing file node is not a symlink %s " % enabled_state)

    # running section
    if state is None:
        pass

    elif enabled:
        if state == 'up' and not is_running:
            rc, message, st = run_command(module, 'up', name, timeout)
            if rc != 0:
                module.fail_json(rc=rc, error=message, status=st)
            else:
                changed = true

        elif state == 'down' and not is_down:
            rc, message, st = run_command(module, 'down', name, timeout)
            if rc != 0:
                module.fail_json(rc=rc, error=message, status=st)
            else:
                changed = true

        elif state == 'once' and not is_running:
            #once needs to be trigger from a down state
            rc, message, st = run_command(module, 'once', name, timeout)
            if rc != 0:
                module.fail_json(rc=rc, error=message, status=st)
            else:
                changed = true

        elif action == 'restart' and (state == 'up' or state == 'once'):
                rc, message, st = run_command(module, 'restart', name, timeout)
                if rc != 0:
                    module.fail_json(rc=rc, error=message, status=st)
                else:
                    changed = true

        elif action == 'reload' and (state == 'up' or state == 'once'):
                rc, message, st = run_command(module, 'reload', name, timeout)
                if rc != 0:
                    module.fail_json(rc=rc, error=message, status=st)
                else:
                    changed = true

    module.exit_json(status=status, changed=changed, run_service_file=run_service_file, log_service_file=log_service_file)


# import module snippets
from ansible.module_utils.basic import *
if __name__ == '__main__':
    main()

