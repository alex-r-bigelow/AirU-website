var mongoose = require('mongoose');

var DeviceSchema = new mongoose.Schema({
  model: String,
  version: String,
  macaddress: String,
  longitude: Number,
  latitude: Number
  // loc: {
  //   type: [Number],  // [<longitude>, <latitude>]
  //   index: '2d'      // create the geospatial index
  // }
});

mongoose.model('Device', DeviceSchema);
