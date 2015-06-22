# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
	config.vm.define "server" do |es|
		es.vm.hostname = "server"
	#	es.vm.box = "hashicorp/precise64"
		es.vm.box = "chef/centos-6.5"
		es.vm.provision :ansible do |ansible|
			ansible.playbook = "test.yml"
		end
		es.vm.network "private_network", ip: "192.168.50.22"
	end
end
