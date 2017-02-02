Development Setup
=================
Prerequisites: Install [VirtualBox](https://www.virtualbox.org/wiki/VirtualBox) and [Vagrant](https://www.vagrantup.com/).

1. Create a file `config/config.json`, with this content (**make sure you never commit this file**; the `.gitignore` should automatically prevent it, but please be aware of the potential to accidentally throw your credentials out on to the open web).

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

2. Once you've created `config.json`, type `vagrant up`; it will set up and start a virtual machine that should be identical to the deployed server (plus any of your changes).

You should be able to access the web interface (use localhost:7080 if you're running in Vagrant, otherwise, it will be served on port 80), and the influxdb API interface (port 8083).

## Notes:
- To sync changes that you make to the vagrant VM, run `vagrant rsync-auto` in this directory; it will watch for changes and propagate them to the VM. To access the VM's command line, type `vagrant ssh`; inside the VM, this directory is synced to `/vagrant`. I've noticed some irregularities with syncing shared folders / forwarded ports: `vagrant plugin install vagrant-vbguest` may help if you encounter these issues.
- If you want to work on the web server, it's probably easiest to halt the system daemon: (from inside the VM:) `sudo systemctl stop web` and start it directly on the console: `sudo -u web; cd /vagrant/web; node app.js`.
  - If, instead, you just want to monitor the process, the log files in `/home/web` should be helpful (feel free to delete them if they get large).
- Similarly, if you want to work on the script that polls data periodically, you'll want to halt the cron daemon: `sudo systemctl stop cron` and run the script directly: `sudo -u poller; cd /vagrant/poll; python poll.py`
  - These log files are stored in `/home/poller` (feel free to trash them as well)

Deployment
==========
This server is designed to work on a fresh Debian system (though it very well could work on other systems). To set up the server, clone the repository somewhere (currently, the air.eng.utah.edu is stored in an `airu` user directory), create the `config/config.json` the same as the Development Setup, and then run `bash deploy.sh` as root.
