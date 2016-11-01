Setup
=====
This server is designed to work on a fresh Debian system (though it very well could work on other systems). To set up the server, run `./deploy.sh`; it should handle everything.

Development
===========
You can work on the server without actually deploying it by using [Vagrant](https://www.vagrantup.com/). With it installed on your local machine, type `vagrant up` in this directory, and you will have a running virtual machine identical to the deployed server (plus any of your changes).

To sync changes that you make to the vagrant VM, run `vagrant rsync-auto` in this directory; it will watch for changes and propagate them to the server. To access the VM's command line, type `vagrant ssh`; inside, this directory is synced to `/vagrant`.
