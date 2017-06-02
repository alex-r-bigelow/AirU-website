var mongoose = require('mongoose');

var SensorSchema = new mongoose.Schema({
  sensor_mac: String,
  sensor_holder: String,
  created_at: { type: Date, default: Date.now },
});

module.exports = mongoose.model('Sensor', SensorSchema);
