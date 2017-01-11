/* globals d3 */

var registeredDevices = [];

function updateRegisteredDevices () {
  var deviceStatusForms = d3.select('#deviceStatusList')
    .selectAll('form').data(registeredDevices);
  deviceStatusForms.exit().remove();
  var newForms = deviceStatusForms.enter().append('form');
  newForms.append('span')
    .html('Device <label class="macAddress"></label> is ' +
          '<label class="onlineStatus"></label>');
  newForms.append('button')
    .text('Remove from database');

  deviceStatusForms = newForms.merge(deviceStatusForms);
  deviceStatusForms.select('label.macAddress').text('<todo: mac address>');
  deviceStatusForms.select('label.onlineStatus').text('online');
}

function updateState () {
  var loggedOut = this.value === 'loggedOut';
  if (loggedOut) {
    registeredDevices = [];
  }
  d3.select('form#login')
    .style('display', loggedOut ? null : 'none');
  d3.select('form#logout')
    .style('display', loggedOut ? 'none' : null);
  d3.select('form#registerUser')
    .style('display', loggedOut ? null : 'none');
  d3.select('form#registerDevice')
    .style('display', loggedOut ? 'none' : null);

  updateRegisteredDevices();
}

window.onload = function () {
  d3.selectAll('input[name=state]').on('change', updateState);
  updateState();
};
