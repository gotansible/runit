Runit
=========

[![Build Status](https://travis-ci.org/gotansible/runit.svg?branch=master)](https://travis-ci.org/gotansible/runit)
[![Ansible Galaxy](http://img.shields.io/badge/galaxy-runit-blue.svg?style=flat)](https://galaxy.ansible.com/list#/roles/3747)

As a role, the [runit](http://smarden.org/runit/) package will be installed. 

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
    required: false
    default: "yes"
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
    required: false (required if auto='yes')
    default: null
    description:
        - The command to run that will start the executable to run. Required if auto='yes'
  user:
    required: false (required if auto='yes')
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
```

Dependencies
------------

None.


About Runit
------------

Runit is a simple service runner who intention is to keep a service running always, 
even if it crashes. A service is defined as an executable that runs on a server.

The way that a runit service is configured, where {{service_name}} is the name of the service that you 
create, is as follows:

Config Files:

/etc/sv/{{service_name}}/run
/etc/sv/{{service_name}}/log/run

The file named 'run' is typically a shell script to launch the executable for your service.

A simple common run file looks like:

```bash
#!/bin/sh

exec 2>&1
exec chpst -e /etc/sv/{{ service_name }}/env -u {{ service_user }} {{ service_command }}

```

A simple rolling log service file looks like:

```bash
#!/bin/sh

exec chpst -u {{ service_user }} svlogd -tt /var/log/{{ service_name }}

```

To enable a service a symlink is created as follows (disabling is simply removing the symlink):

/etc/service/{{service_name}} ------> /etc/sv/{{service_name}}

To manually start a service:

```
  sudo sv start {{service_Name}}
```

To manually get the service status:

```
  sudo sv status {{service_Name}}
```

Task Comments
----------------

If auto='yes' the above config files will be created for you and you'll need to set the 'command' to run and the 'user' to run the service under.

If you would like to control the details of the files, simply set auto='no', enabled='no', create the two run files and place 
them in the correct service location (/etc/sv/{{service_name}}/run ...).  For your convenience the file
config paths are returned as 'run_service_file' and 'log_service_file'. After your custom run files are in place set enabled='yes', state='up'.


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
		register: myservice_status
	  
### handler.yml
	  - name: restart myservice
		runit: name=myservice enabled=true state=up timeout=9 action=restart
		when: not myservice_status.restarted

License
-------

MIT

Author Information
------------------

Created by Franklin Wise in Santa Monica, CA.

