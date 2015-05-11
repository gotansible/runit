# reference:https://github.com/ansible/ansible/blob/5dce745868720379f69c7b307a3addeafbea66e3/v2/ansible/plugins/action/template.py
# https://github.com/ansible/ansible/blob/f310d132806dd6870a92cd93b2a8983c24ff548d/v2/ansible/template/__init__.py#L20
# stopped at can't call template module

import time
import os
from ansible import utils
from ansible import errors
#from ansible.utils import template
from ansible.runner.return_data import ReturnData

#from ansible.plugins.action import ActionBase
#from ansible.utils import Template
#from ansible.template import Templar
from ansible.utils.hashing import checksum_s

def _generate_timestamp():
    return time.strftime("%Y%m%d%H%M%S")


class ActionModule(object):

    TRANSFERS_FILES = True

    def __init__(self, runner):
        self.runner = runner
        self.basedir = runner.basedir

    def _merge_args(self, module_args, complex_args):
        args = {}
        if complex_args:
            args.update(complex_args)

        kv = utils.parse_kv(module_args)
        args.update(kv)

        return args

    def _is_true(self, val):
        if val == 'yes' or val == 'true' or val == True or val is None:
            return True
        else:
            return False

    def run(self, conn, tmp, module_name, module_args, inject, complex_args=None, **kwargs):
        if not self.runner.is_playbook:
            raise errors.AnsibleError("in current versions of ansible, templates are only usable in playbooks")

        # load up options
        options  = self._merge_args(module_args, complex_args)

        src_run = options.get('src_run', None)
        src_log = options.get('src_log', None)

        if 'src_run' in options: del options['src_run']
        if 'src_log' in options: del options['src_log']

        auto = self._is_true(options.get('auto'))
        enabled = self._is_true(options.get('enabled'))

        if not auto:
            if (src_run is None or src_log is None):
                result = dict(failed=True, msg="src_run and src_log are required")
                return ReturnData(conn=conn, comm_ok=False, result=result)

            options['enabled'] = 'no'
            runit_args = ''.join("{}='{}' ".format(key, val) for key, val in options.items())

            runit_return = self.runner._execute_module(conn, tmp, 'runit', runit_args, inject=inject, complex_args=complex_args, persist_files=True)
            run_service_file = runit_return.result.get('run_service_file')


            # TODO: unable to call template from here
            # _execute_module is looking for a file with a shebang and for whatever odd reason, the template
            # module is empty and implemented somewhere else
            if not run_service_file is None:
                template_args = "dest='%s' src='%s' group='root' user='root' mode='0755'" % (run_service_file, src_run )
                self.do_template(src_run, run_service_file)
                template_return = self.runner._execute_module(conn, tmp, 'template', template_args, inject=inject, complex_args=complex_args, persist_files=True)
#                raise errors.AnsibleError(template_return)
                if 'failure_var' in template_return:
                    return tempalte_return
            else:
                return runit_return

            if 'log_service_file' in runit_return.result:
                template_args = "dest='%s' src=src_run group='root' user='root' mode='0755'" % log_service_file
                template_return = self.runner._execute_module(conn, tmp, 'template', module_args, inject=inject, complex_args=complex_args, persist_files=True)
                if 'failure_var' in template_return:
                    return tempalte_return
            else:
                return runit_return


        if auto or module_args['enabled']:
            if enabled:
                options['enabled'] = 'yes'
            runit_args = ''.join("{}='{}' ".format(key, val) for key, val in options.items())
            return self.runner._execute_module(conn, tmp, 'runit', runit_args, inject=inject, complex_args=complex_args, persist_files=True)

    ## The following was Stolen from ansible/v2/ansible/plugins/action/template.py
    ## since it's totally unclear to me how to accomplish this otherwise

    def get_checksum(self, tmp, dest, try_directory=False, source=None):
        remote_checksum = self._remote_checksum(tmp, dest)

        if remote_checksum in ('0', '2', '3', '4'):
            # Note: 1 means the file is not present which is fine; template
            # will create it.  3 means directory was specified instead of file
            if try_directory and remote_checksum == '3' and source:
                base = os.path.basename(source)
                dest = os.path.join(dest, base)
                remote_checksum = self.get_checksum(tmp, dest, try_directory=False)
                if remote_checksum not in ('0', '2', '3', '4'):
                    return remote_checksum

            result = dict(failed=True, msg="failed to checksum remote file."
                        " Checksum error code: %s" % remote_checksum)
            return result

        return remote_checksum

    def do_template(self, source, dest, tmp=None, task_vars=dict()):
        ''' handler for template operations '''

        #source = self._task.args.get('src', None)
        #dest   = self._task.args.get('dest', None)

        if (source is None and 'first_available_file' not in task_vars) or dest is None:
            return dict(failed=True, msg="src and dest are required")

        if tmp is None:
            tmp = "/tmp/tmp"# self._make_tmp_path()

        #if self._task._role is not None:
        #    source = self._loader.path_dwim_relative(self._task._role._role_path, 'templates', source)
        #else:
        #    source = self._loader.path_dwim(source)

        # Expand any user home dir specification
        #dest = self._remote_expand_user(dest, tmp)

        directory_prepended = False
        if dest.endswith(os.sep):
            directory_prepended = True
            base = os.path.basename(source)
            dest = os.path.join(dest, base)

        # template the source data locally & get ready to transfer
        templar = Templar(loader=self._loader, variables=task_vars)
        try:
            with open(source, 'r') as f:
                template_data = f.read()
            resultant = templar.template(template_data, preserve_trailing_newlines=True)
        except Exception as e:
            return dict(failed=True, msg=type(e).__name__ + ": " + str(e))

        local_checksum = checksum_s(resultant)
        remote_checksum = self.get_checksum(tmp, dest, not directory_prepended, source=source)
        if isinstance(remote_checksum, dict):
            # Error from remote_checksum is a dict.  Valid return is a str
            return remote_checksum

        if local_checksum != remote_checksum:
            # if showing diffs, we need to get the remote value
            dest_contents = ''

            xfered = self._transfer_data(self._shell.join_path(tmp, 'source'), resultant)

            # fix file permissions when the copy is done as a different user
            if self._connection_info.become and self._connection_info.become_user != 'root':
                self._remote_chmod('a+r', xfered, tmp)

            # run the copy module
            new_module_args = self._task.args.copy()
            new_module_args.update(
               dict(
                   src=xfered,
                   dest=dest,
                   original_basename=os.path.basename(source),
                   follow=True,
                ),
            )

            result = self._execute_module(module_name='copy', module_args=new_module_args)
            if result.get('changed', False):
                result['diff'] = dict(before=dest_contents, after=resultant)
            return result

        else:
            # when running the file module based on the template data, we do
            # not want the source filename (the name of the template) to be used,
            # since this would mess up links, so we clear the src param and tell
            # the module to follow links.  When doing that, we have to set
            # original_basename to the template just in case the dest is
            # a directory.
            new_module_args = self._task.args.copy()
            new_module_args.update(
                dict(
                    src=None,
                    original_basename=os.path.basename(source),
                    follow=True,
                ),
            )
            return self._execute_module(module_name='file', module_args=new_module_args)
