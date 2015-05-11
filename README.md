Runit
=========

As a role, the runit package will be installed. 

As a task, an instance of a named runit service instance will be created.

Requirements
------------

Systems: 

* Debian (Ubuntu) 
* RedHat (CentOS) 

Role Variables
--------------

None.

Task Variables
--------------
```
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
        if disabled the service will not be running and will not start on system boot
  timeout:
    description:
        - The number of seconds to wait for the service to start or stop before timing out
    required: false
    default: 7
  manual:
    required: false
    default: "no"
    choices: [ "yes", "no" ]
    description:
        - if manual is true, the caller is required to create the run file and the run log file.
        - See the notes for a more detailed explanation.
  command:
    description:
        - The command to run that will start the executable to run
    required: true
    default: null
  user:
    description:
        - The user that the service will run under. It is recommended that this value be set if manual='yes'
    required: false
    default: "root"
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
```

Dependencies
------------

None.


Notes
------------
As a role, the runit package is installed and started.

As a task, the necessary folders and files will be created to run your service.

Due to the nature of runit, enabed='yes' will cause runit to start.
	 
In the manual='yes' mode you must provide a command for the run file to run when you
want your service to start. However, if you want more control, you can set
manual='yes' and use the returned vars of run_service_file and log_service_file and
generate your own run files for both. Note, that in the case of using your own
run file, you'll need to run this module in the enabled='false' state, then generate your
files to the locations specified by the run_service_file and log_service_file and then enable
the service after the custom run files have been place in their correct paths. In the case
of this manual mode, the 'user' and 'command' values are not used

If the service is not enabled, state and action values are ignored.


Example Playbook
----------------
See test.yml for a working version.

    - hosts: servers
	  sudo: true

      roles:
         - { role: gotansible.runit }

	  tasks:
      - name: place file to run
        copy: src=testrun.sh dest=/opt/runme mode=0755

      - name: create log dir
        file: state=directory path=/var/log/myservice

      - name: test runit
        runit: name=myservice enabled=true state=up timeout=9 user='root' command='bash /opt/runme'


License
-------

MIT

Author Information
------------------

Created by Franklin Wise in Santa Monica, CA.

