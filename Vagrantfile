# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|

  config.vm.box = "debian/jessie64"
  config.vm.synced_folder ".", "/vagrant", type: "rsync", rsync__exclude: [".vagrant/","web/node_modules"]
  config.vm.provision :shell, path:"deploy.sh", args: ["/vagrant"]
  config.vm.network :forwarded_port, guest: 8083, host: 8083
  config.vm.network :forwarded_port, guest: 8086, host: 8086
  config.vm.network :forwarded_port, guest: 27017, host: 27017
  config.vm.network :forwarded_port, guest: 80, host: 7080
  config.ssh.shell = "bash -c 'BASH_ENV=/etc/profile exec bash'"

end
