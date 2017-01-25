Development Setup
=================
Prerequisites: Install [VirtualBox]() and [Vagrant]().

1. Create a file `config/config.json`, with this content (this should be ignored in any git commits).

  ```json
  {
    "email": "air@eng.utah.edu",
    "emailPassword": "changeme",
    "smtpHost": "mailgate.eng.utah.edu",
    "influxdbUsername": "admin",
    "influxdbPassword": "changeme",
    "host": "http://air.eng.utah.edu"
  }
  ```

  Some details about each of these settings:
  - email: A secure email address that you own (this address will be used to send out user authentication credentials)
  - emailPassword: The password for that email address
  - smtpHost: The SMTP server for that email address
  - influxdbUsername: A username to administer the influxDB database
  - influxdbPassword: The password for that account
  - host: The address of the server where this is being deployed (if setting up in Vagrant, use "http://localhost", otherwise, use the public name, e.g. "http://air.eng.utah.edu")

2. Once you've created `config.json`, type `vagrant up`; it should handle everything.

You should be able to access the web interface (use localhost:7080 if you're running in Vagrant, otherwise, it will be served on port 80), and the influxdb API interface (port 8083).

## Notes:
To sync changes that you make to the vagrant VM, run `vagrant rsync-auto` in this directory; it will watch for changes and propagate them to the VM. To access the VM's command line, type `vagrant ssh`; inside the VM, this directory is synced to `/vagrant`.

To restart the web server (from inside the VM): `sudo systemctl restart web`

*Note:* I've noticed some irregularities with syncing shared folders / forwarded ports. `vagrant plugin install vagrant-vbguest` may help if you encounter these issues.

Deployment
==========
This server is designed to work on a fresh Debian system (though it very well could work on other systems). To set up the server, clone the repository somewhere (currently, the air.eng.utah.edu is stored in an `airu` user directory), create the `config/config.json` the same as the Development Setup, and then run `bash deploy.sh` as root.

Development
===========
**WARNING:** Make sure that credentials in config/config.json are excluded from any commits. I've added a rule to the `.gitignore` file to help us avoid accidentally committing credentials, but be aware that that is there.

You can work on the server without actually deploying it by using [Vagrant](https://www.vagrantup.com/). With it installed on your local machine, type `vagrant up` in this directory (this will run `deploy.sh` for you inside the VM), and you will have a running virtual machine that should be identical to the deployed server (plus any of your changes).

To sync changes that you make to the vagrant VM, run `vagrant rsync-auto` in this directory; it will watch for changes and propagate them to the VM. To access the VM's command line, type `vagrant ssh`; inside the VM, this directory is synced to `/vagrant`.

To restart the web server (from inside the VM): `sudo systemctl restart web`

*Note:* I've noticed some irregularities with syncing shared folders / forwarded ports. `vagrant plugin install vagrant-vbguest` may help if you encounter these issues.
