#!/usr/bin/python
# -*- coding: utf-8 -*-

#import shutil
#import stat
#import grp
#import pwd
import os
import tempfile

#try:
#    import selinux
#    HAVE_SELINUX=True
#except ImportError:
#    HAVE_SELINUX=False

DOCUMENTATION = '''
---
module: runit
version_added: "1.9.1"
short_description: Installs runit and sets up a runit service
description:
    - As a role it installs runit. As a task it creates a new runit service
    service entry.
notes:
    - if you want complete control of the startup script, you can just do it yourself
requirements: [ ]
author: Franklin Wise
options:
  name:
    description:
        - The name of the service, directories will be created with this a name and this name
        will be used to start and stop the service
    required: true
    default: []
  state:
    description:
        - If up the service will start providing it's 'Enabled'
        If down the service will be stopped providing it's running and 'Enabled'
        If once the service will start, however, it if crashes, it will stay down
        proving it is 'Enabled'
    required: true
    choices: [ "up", "down", "once" ]
  enabled:
    required: false
    default: "yes"
    choices: [ "yes", "no" ]
    description:
        - if enabled the service will be running and also will start on system boot
        if disabled the servie will not be running and will not start on system boot
  timeout:
    description:
        - The number of seconds to wait for the service to start or stop before timing out
    required: false
    default: 7
  command:
    description:
        - The command to run that will start the executable to run
    required: true
    default: null
  env_vars:
    description:
        - A hash of key value pairs of environmental variables that should be available for the service
    required: false
    default: null
  action:
    required: false
    default: null
    choices: [ "restart", "reload" ]
    description:
      - if the service is up and enabled causes the given action to take place.
        restart will stop the servie and the start it
        reload will send the HUP signal to cause a config reload
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
        #return False


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
            command = dict(required=False, default=None),
            action = dict(required=False, choices=['restart','reload'], default=None),
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
    command = params['command']
    action = params['action']
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

    # do file diff, if different, swap, mark as changed

    log_command = '''
#!/bin/sh
exec chpst -u %s svlogd -tt /var/log/%s
    ''' % ('root', name)

    command_text = '''
#!/bin/sh
exec 2>&1
exec chpst -e /etc/sv/%s/env -u %s %s
    ''' % (name, 'root', command)

    # create run
    changed |= write_file(module, command_text,'%s/run' % (service_dir ))
    # create log/run
    changed |= write_file(module, log_command,'%s/run' % (service_log_dir ))
    # create each file for ENV
    if not env_vars is None:
        for k, v in env_vars:
            changed |= write_file(module, contents,'%s/%s' % (service_env_dir, k ))

    enabled_service_dir = '/etc/service/%s' % name
    # enabled section
    # could handle edge cases like if the service folder exists, but is not a symlink etc.
    enabled_state = get_file_state(enabled_service_dir)

    if enabled is None:
        pass

    elif enabled and enabled_state != 'link':
        if enabled_state == 'absent':
            try:
                os.symlink(service_dir + '/', enabled_service_dir)
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

    elif state == 'up' and not is_running:
        rc, message, status = run_command(module, 'up', name, timeout)
        if rc != 0:
            module.fail_json(rc=rc, error=message, status=status)
        else:
            changed = true

    elif state == 'down' and not is_down:
        rc, message, status = run_command(module, 'down', name, timeout)
        if rc != 0:
            module.fail_json(rc=rc, error=message, status=status)
        else:
            changed = true

    elif state == 'once' and not is_running:
        rc, message, status = run_command(module, 'once', name, timeout)
        if rc != 0:
            module.fail_json(rc=rc, error=message, status=status)
        else:
            changed = true

    if enabled and (state == 'up' or state == 'once'):
        if action == 'restart':
            rc, message, status = run_command(module, 'restart', name, timeout)
            if rc != 0:
                module.fail_json(rc=rc, error=message, status=status)
            else:
                changed = true

    if enabled and state == 'up':
        if action == 'reload':
            rc, message, status = run_command(module, 'reload', name, timeout)
            if rc != 0:
                module.fail_json(rc=rc, error=message, status=status)
            else:
                changed = true


#    variables=dict(name=name)
#    templar = Templar(loader=self._loader, variables=variables, fail_on_undefined=True)
#    # todo template
#    template_path = '/etc/sv/init.d'
#    if os.path.exists(template_path):
#        with open(template_path, 'r') as f:
#            template_data = f.read()
#            lines = templar.template(template_data, preserve_trailing_newlines=False)
#            write_file(module,lines, '/etc/init.d/%s' % name)
#    else:
#        raise AnsibleError("the template file %s could not be found for the lookup" % term)
#        return ret

    module.exit_json(state=state, changed=changed)


# import module snippets
from ansible.module_utils.basic import *
#from ansible.template import Templar
#from ansible.plugins.action import ActionModule as Template
if __name__ == '__main__':
    main()

