Setup
=====
This server is designed to work on a fresh Debian system (though it very well could work on other systems). To set up the server:

Edit every entry in `config/config.json`. Some details about each of these:
- TODO

Once `config.json` has been set up, run `./deploy.sh`; it should handle everything.

Development
===========
You can work on the server without actually deploying it by using [Vagrant](https://www.vagrantup.com/). With it installed on your local machine, type `vagrant up` in this directory, and you will have a running virtual machine identical to the deployed server (plus any of your changes).

To sync changes that you make to the vagrant VM, run `vagrant rsync-auto` in this directory; it will watch for changes and propagate them to the server. To access the VM's command line, type `vagrant ssh`; inside, this directory is synced to `/vagrant`.

I've noticed some irregularities with shared folders / forwarded ports (handy if, for example, you want to access the VM's mongo database from the host machine). `vagrant plugin install vagrant-vbguest` may help if you encounter these issues.
